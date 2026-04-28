from __future__ import annotations

import asyncio
from dataclasses import dataclass

from telegram.ext import Application

from app.bot.downloader_execution_runtime import (
    ResolvedDownloaderExecution,
    resolve_bound_downloader_execution as resolve_shared_bound_downloader_execution,
)
from app.bot.download_follow_up_runtime import (
    start_download_follow_up_scheduler,
    stop_download_follow_up_scheduler,
)
from app.bot.execution_runtime import resolve_execution_gate
from app.bot.feishu_long_connection import (
    FEISHU_LONG_CONNECTION_SERVICE_KEY,
    FeishuLongConnectionService,
)
from app.bot.personal_wechat_login import PersonalWeChatLoginService
from app.bot.wecom_webhook_server import (
    WeComWebhookServerConfig,
    WeComWebhookServerRuntime,
    start_wecom_webhook_server,
    stop_wecom_webhook_server,
)
from app.operational_logging import emit_operational_log
from app.services.manage_bt_subscription import (
    BtSubscriptionDispatchContext,
    ManageBtSubscriptionService,
)
from app.runtime.execution_policy import ACTION_BT_SUBSCRIPTION_RUN, ExecutionGate


DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE = "下载器角色 {role} 绑定的实例不存在：{name}。请检查配置后重试。"
GET_DOWNLOAD_STATUS_SERVICE_KEY = "get_download_status_service"
MANAGE_BT_SUBSCRIPTION_SERVICE_KEY = "manage_bt_subscription_service"
EXECUTION_GATE_KEY = "execution_gate"
DOWNLOADER_INSTANCES_KEY = "downloader_instances"
DOWNLOADER_ROLE_BINDING_KEY = "downloader_role_binding"
BT_SUBSCRIPTION_SCHEDULER_TASK_KEY = "bt_subscription_scheduler_task"
BT_SUBSCRIPTION_SCHEDULER_STOP_EVENT_KEY = "bt_subscription_scheduler_stop_event"
POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY = "post_download_auto_import_task"
POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY = "post_download_auto_import_stop_event"
DOWNLOAD_COMPLETION_POLLING_TASK_KEY = "download_completion_polling_task"
DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY = "download_completion_polling_stop_event"
WECOM_WEBHOOK_SERVER_CONFIG_KEY = "wecom_webhook_server_config"
WECOM_WEBHOOK_SERVER_RUNTIME_KEY = "wecom_webhook_server_runtime"
POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY = "post_download_auto_import_service"
BT_SUBSCRIPTION_SCHEDULER_INTERVAL_SECONDS = 300.0
POST_DOWNLOAD_AUTO_IMPORT_INTERVAL_SECONDS = 300.0


@dataclass(frozen=True, slots=True)
class TelegramSidecarRuntimeConfig:
    post_download_auto_import_service_key: str
    post_download_auto_import_stop_event_key: str
    post_download_auto_import_task_key: str
    get_download_status_service_key: str
    download_completion_polling_stop_event_key: str
    download_completion_polling_task_key: str
    wecom_webhook_server_config_key: str
    wecom_webhook_server_runtime_key: str
    personal_wechat_login_service_key: str
    post_download_auto_import_interval_seconds: float


TELEGRAM_SIDECAR_RUNTIME_CONFIG = TelegramSidecarRuntimeConfig(
    post_download_auto_import_service_key=POST_DOWNLOAD_AUTO_IMPORT_SERVICE_KEY,
    post_download_auto_import_stop_event_key=POST_DOWNLOAD_AUTO_IMPORT_STOP_EVENT_KEY,
    post_download_auto_import_task_key=POST_DOWNLOAD_AUTO_IMPORT_TASK_KEY,
    get_download_status_service_key=GET_DOWNLOAD_STATUS_SERVICE_KEY,
    download_completion_polling_stop_event_key=DOWNLOAD_COMPLETION_POLLING_STOP_EVENT_KEY,
    download_completion_polling_task_key=DOWNLOAD_COMPLETION_POLLING_TASK_KEY,
    wecom_webhook_server_config_key=WECOM_WEBHOOK_SERVER_CONFIG_KEY,
    wecom_webhook_server_runtime_key=WECOM_WEBHOOK_SERVER_RUNTIME_KEY,
    personal_wechat_login_service_key="personal_wechat_login_service",
    post_download_auto_import_interval_seconds=POST_DOWNLOAD_AUTO_IMPORT_INTERVAL_SECONDS,
)


async def start_telegram_sidecars(application: Application, *, config: TelegramSidecarRuntimeConfig) -> None:
    _start_wecom_webhook_server_if_configured(application, config=config)
    await _start_feishu_long_connection_if_configured(application)
    await _start_personal_wechat_text_service_if_available(application)
    _start_post_download_auto_import_scheduler(application, config=config)


async def stop_telegram_sidecars(application: Application, *, config: TelegramSidecarRuntimeConfig) -> None:
    _stop_wecom_webhook_server_if_running(application, config=config)
    await _shutdown_feishu_long_connection_if_running(application)
    await _shutdown_personal_wechat_text_service_if_running(application)
    await _shutdown_personal_wechat_login_service_if_running(application, config=config)
    await _stop_post_download_auto_import_scheduler(application, config=config)


async def start_telegram_application_lifecycle(application: Application) -> None:
    await start_telegram_sidecars(application, config=TELEGRAM_SIDECAR_RUNTIME_CONFIG)

    existing_task = application.bot_data.get(BT_SUBSCRIPTION_SCHEDULER_TASK_KEY)
    if isinstance(existing_task, asyncio.Task) and not existing_task.done():
        return

    bt_subscription_service = application.bot_data.get(MANAGE_BT_SUBSCRIPTION_SERVICE_KEY)
    if not isinstance(bt_subscription_service, ManageBtSubscriptionService):
        return

    downloader_execution, resolution_error = _resolve_bound_downloader_execution_for_application(
        application=application,
        role="bt",
    )
    if resolution_error is not None:
        _log_bt_subscription_scheduler_config_error(reason=resolution_error)
        return
    if downloader_execution is None:
        _log_bt_subscription_scheduler_config_error(reason="未配置 BT 下载器角色绑定，后台自动扫描不会启动。")
        return

    stop_event = asyncio.Event()
    application.bot_data[BT_SUBSCRIPTION_SCHEDULER_STOP_EVENT_KEY] = stop_event
    application.bot_data[BT_SUBSCRIPTION_SCHEDULER_TASK_KEY] = application.create_task(
        _bt_subscription_scheduler_loop(
            application=application,
            bt_subscription_service=bt_subscription_service,
            execution_gate=_resolve_execution_gate_for_application(application),
            stop_event=stop_event,
            dispatch_context=BtSubscriptionDispatchContext(
                downloader_name=downloader_execution.name,
                downloader_type=downloader_execution.downloader_type,
                download_dir=downloader_execution.download_dir,
            ),
        ),
        name="bt_subscription_scheduler",
    )


async def stop_telegram_application_lifecycle(application: Application) -> None:
    await stop_telegram_sidecars(application, config=TELEGRAM_SIDECAR_RUNTIME_CONFIG)

    stop_event = application.bot_data.pop(BT_SUBSCRIPTION_SCHEDULER_STOP_EVENT_KEY, None)
    task = application.bot_data.pop(BT_SUBSCRIPTION_SCHEDULER_TASK_KEY, None)
    if isinstance(stop_event, asyncio.Event):
        stop_event.set()
    if not isinstance(task, asyncio.Task):
        return
    try:
        await task
    except Exception as error:
        _log_bt_subscription_scheduler_loop_error(error=error)


def _resolve_execution_gate_for_application(application: Application) -> ExecutionGate:
    return resolve_execution_gate(
        bot_data=application.bot_data,
        execution_gate_key=EXECUTION_GATE_KEY,
    )


def _resolve_bound_downloader_execution_for_application(
    *,
    application: Application,
    role: str,
) -> tuple[ResolvedDownloaderExecution | None, str | None]:
    return resolve_shared_bound_downloader_execution(
        bot_data=application.bot_data,
        role=role,
        downloader_role_binding_key=DOWNLOADER_ROLE_BINDING_KEY,
        downloader_instances_key=DOWNLOADER_INSTANCES_KEY,
        config_missing_template=DOWNLOADER_EXECUTION_CONFIG_MISSING_TEMPLATE,
    )


async def _bt_subscription_scheduler_loop(
    *,
    application: Application,
    bt_subscription_service: ManageBtSubscriptionService,
    execution_gate: ExecutionGate,
    stop_event: asyncio.Event,
    dispatch_context: BtSubscriptionDispatchContext,
) -> None:
    while not stop_event.is_set():
        try:
            await _run_bt_subscription_scheduler_tick_once(
                application=application,
                bt_subscription_service=bt_subscription_service,
                execution_gate=execution_gate,
                dispatch_context=dispatch_context,
            )
        except Exception as error:
            _log_bt_subscription_scheduler_loop_error(error=error)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=BT_SUBSCRIPTION_SCHEDULER_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def _run_bt_subscription_scheduler_tick_once(
    *,
    application: Application,
    bt_subscription_service: ManageBtSubscriptionService,
    execution_gate: ExecutionGate,
    dispatch_context: BtSubscriptionDispatchContext,
) -> None:
    notifications = await execution_gate.run(
        ACTION_BT_SUBSCRIPTION_RUN,
        lambda: bt_subscription_service.run_scheduler_tick(
            dispatch_context=dispatch_context,
        ),
    )
    if notifications is None:
        _log_bt_subscription_scheduler_result_unavailable()
        return
    for chat_id, reply_text in notifications:
        await _send_bt_subscription_scheduler_message(
            application=application,
            chat_id=chat_id,
            text=reply_text,
        )


async def _send_bt_subscription_scheduler_message(
    *,
    application: Application,
    chat_id: int,
    text: str,
) -> None:
    try:
        await application.bot.send_message(chat_id=chat_id, text=text)
    except Exception as error:
        _log_bt_subscription_scheduler_send_error(chat_id=chat_id, error=error)


def _log_bt_subscription_scheduler_config_error(*, reason: str) -> None:
    emit_operational_log(
        title="BT 订阅后台扫描未启动",
        detail=f"原因={reason}",
        fix_hint="检查 BT 下载器角色绑定和下载器实例配置后重启应用。",
    )


def _log_bt_subscription_scheduler_loop_error(*, error: Exception) -> None:
    emit_operational_log(
        title="BT 订阅后台扫描失败",
        detail=f"原因={error}",
        fix_hint="检查 Prowlarr、SQLite 和 Telegram 发送链路后等待下一轮自动扫描。",
    )


def _log_bt_subscription_scheduler_result_unavailable() -> None:
    emit_operational_log(
        title="BT 订阅后台扫描结果不可用",
        detail="本轮未生成可发送通知。",
        fix_hint="检查 Prowlarr、SQLite、approval_record/jobs 和前面的后台扫描明细日志；当前这轮通知已跳过，下一轮自动扫描仍会继续尝试。",
    )


def _log_bt_subscription_scheduler_send_error(*, chat_id: int, error: Exception) -> None:
    emit_operational_log(
        title="BT 订阅后台通知失败",
        detail=f"chat_id={chat_id} 原因={error}",
        fix_hint="检查 Telegram Bot Token、聊天可达性和网络连通性后等待下一轮自动扫描。",
    )


def _start_post_download_auto_import_scheduler(application: Application, *, config: TelegramSidecarRuntimeConfig) -> None:
    start_download_follow_up_scheduler(
        application=application,
        post_download_auto_import_service_key=config.post_download_auto_import_service_key,
        post_download_auto_import_stop_event_key=config.post_download_auto_import_stop_event_key,
        post_download_auto_import_task_key=config.post_download_auto_import_task_key,
        get_download_status_service_key=config.get_download_status_service_key,
        download_completion_polling_stop_event_key=config.download_completion_polling_stop_event_key,
        download_completion_polling_task_key=config.download_completion_polling_task_key,
        interval_seconds=config.post_download_auto_import_interval_seconds,
    )


async def _stop_post_download_auto_import_scheduler(
    application: Application,
    *,
    config: TelegramSidecarRuntimeConfig,
) -> None:
    await stop_download_follow_up_scheduler(
        application=application,
        post_download_auto_import_stop_event_key=config.post_download_auto_import_stop_event_key,
        post_download_auto_import_task_key=config.post_download_auto_import_task_key,
        download_completion_polling_stop_event_key=config.download_completion_polling_stop_event_key,
        download_completion_polling_task_key=config.download_completion_polling_task_key,
    )


async def _start_feishu_long_connection_if_configured(application: Application) -> None:
    service = application.bot_data.get(FEISHU_LONG_CONNECTION_SERVICE_KEY)
    if not isinstance(service, FeishuLongConnectionService):
        return
    await service.start(bot_data=application.bot_data)


async def _shutdown_feishu_long_connection_if_running(application: Application) -> None:
    service = application.bot_data.get(FEISHU_LONG_CONNECTION_SERVICE_KEY)
    if not isinstance(service, FeishuLongConnectionService):
        return
    await service.shutdown()


def _start_wecom_webhook_server_if_configured(application: Application, *, config: TelegramSidecarRuntimeConfig) -> None:
    existing_runtime = application.bot_data.get(config.wecom_webhook_server_runtime_key)
    if isinstance(existing_runtime, WeComWebhookServerRuntime):
        return

    server_config = application.bot_data.get(config.wecom_webhook_server_config_key)
    if server_config is None:
        return
    if not isinstance(server_config, WeComWebhookServerConfig):
        emit_operational_log(
            title="WeCom webhook 配置不完整",
            detail="缺少有效的 server config。",
            fix_hint="同时配置 WECOM_TOKEN/WECOM_ENCODING_AES_KEY/WECOM_RECEIVE_ID，并在启动阶段注入 webhook host/port/path。",
        )
        return
    try:
        runtime = start_wecom_webhook_server(
            loop=asyncio.get_running_loop(),
            config=server_config,
            bot_data=application.bot_data,
        )
    except OSError as error:
        emit_operational_log(
            title="WeCom webhook 启动失败",
            detail=f"原因={error}",
            fix_hint="检查 WECOM_WEBHOOK_HOST/PORT 是否可绑定，或确认端口未被占用。",
        )
        raise
    application.bot_data[config.wecom_webhook_server_runtime_key] = runtime


def _stop_wecom_webhook_server_if_running(application: Application, *, config: TelegramSidecarRuntimeConfig) -> None:
    runtime = application.bot_data.pop(config.wecom_webhook_server_runtime_key, None)
    if not isinstance(runtime, WeComWebhookServerRuntime):
        return
    stop_wecom_webhook_server(runtime)


async def _start_personal_wechat_text_service_if_available(application: Application) -> None:
    from app.bot.personal_wechat_text import (
        PERSONAL_WECHAT_TEXT_SERVICE_KEY,
        PersonalWeChatTextService,
    )

    service = application.bot_data.get(PERSONAL_WECHAT_TEXT_SERVICE_KEY)
    if service is None:
        service = PersonalWeChatTextService()
        application.bot_data[PERSONAL_WECHAT_TEXT_SERVICE_KEY] = service
    if not isinstance(service, PersonalWeChatTextService):
        emit_operational_log(
            title="personal WeChat 私聊文本服务配置无效",
            detail="bot_data 中的 personal_wechat_text_service 不是有效服务实例。",
            fix_hint="删除错误注入值，或改为 PersonalWeChatTextService 实例后重启服务。",
        )
        return
    await service.start(bot_data=application.bot_data)


async def _shutdown_personal_wechat_text_service_if_running(application: Application) -> None:
    from app.bot.personal_wechat_text import (
        PERSONAL_WECHAT_TEXT_SERVICE_KEY,
        PersonalWeChatTextService,
    )

    service = application.bot_data.get(PERSONAL_WECHAT_TEXT_SERVICE_KEY)
    if not isinstance(service, PersonalWeChatTextService):
        return
    await service.shutdown()


async def _shutdown_personal_wechat_login_service_if_running(
    application: Application,
    *,
    config: TelegramSidecarRuntimeConfig,
) -> None:
    service = application.bot_data.get(config.personal_wechat_login_service_key)
    if not isinstance(service, PersonalWeChatLoginService):
        return
    await service.shutdown()
