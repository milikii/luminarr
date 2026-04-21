from __future__ import annotations

import asyncio
from dataclasses import dataclass

from telegram.ext import Application

from app.bot.download_follow_up_runtime import (
    start_download_follow_up_scheduler,
    stop_download_follow_up_scheduler,
)
from app.bot.feishu_long_connection import (
    FEISHU_LONG_CONNECTION_SERVICE_KEY,
    FeishuLongConnectionService,
)
from app.bot.feishu_webhook_server import (
    FeishuWebhookServerConfig,
    FeishuWebhookServerRuntime,
    start_feishu_webhook_server,
    stop_feishu_webhook_server,
)
from app.bot.personal_wechat_login import PersonalWeChatLoginService
from app.bot.wecom_webhook_server import (
    WeComWebhookServerConfig,
    WeComWebhookServerRuntime,
    start_wecom_webhook_server,
    stop_wecom_webhook_server,
)


@dataclass(frozen=True, slots=True)
class TelegramSidecarRuntimeConfig:
    post_download_auto_import_service_key: str
    post_download_auto_import_stop_event_key: str
    post_download_auto_import_task_key: str
    get_download_status_service_key: str
    download_completion_polling_stop_event_key: str
    download_completion_polling_task_key: str
    feishu_webhook_server_config_key: str
    feishu_webhook_reply_text_func_key: str
    feishu_webhook_server_runtime_key: str
    wecom_webhook_server_config_key: str
    wecom_webhook_server_runtime_key: str
    personal_wechat_login_service_key: str
    post_download_auto_import_interval_seconds: float


async def start_telegram_sidecars(application: Application, *, config: TelegramSidecarRuntimeConfig) -> None:
    _start_feishu_webhook_server_if_configured(application, config=config)
    _start_wecom_webhook_server_if_configured(application, config=config)
    await _start_feishu_long_connection_if_configured(application)
    await _start_personal_wechat_text_service_if_available(application)
    _start_post_download_auto_import_scheduler(application, config=config)


async def stop_telegram_sidecars(application: Application, *, config: TelegramSidecarRuntimeConfig) -> None:
    _stop_feishu_webhook_server_if_running(application, config=config)
    _stop_wecom_webhook_server_if_running(application, config=config)
    await _shutdown_feishu_long_connection_if_running(application)
    await _shutdown_personal_wechat_text_service_if_running(application)
    await _shutdown_personal_wechat_login_service_if_running(application, config=config)
    await _stop_post_download_auto_import_scheduler(application, config=config)


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


def _start_feishu_webhook_server_if_configured(application: Application, *, config: TelegramSidecarRuntimeConfig) -> None:
    existing_runtime = application.bot_data.get(config.feishu_webhook_server_runtime_key)
    if isinstance(existing_runtime, FeishuWebhookServerRuntime):
        return

    server_config = application.bot_data.get(config.feishu_webhook_server_config_key)
    reply_text_func = application.bot_data.get(config.feishu_webhook_reply_text_func_key)
    if server_config is None and reply_text_func is None:
        return
    if not isinstance(server_config, FeishuWebhookServerConfig) or not callable(reply_text_func):
        print(
            "\033[31m[Feishu webhook 配置不完整]\033[0m 缺少 server config 或 reply sender。\n"
            "\033[33m[处理建议]\033[0m 同时配置 FEISHU_APP_ID/FEISHU_APP_SECRET，并在启动阶段注入 webhook host/port/path。"
        )
        return
    try:
        runtime = start_feishu_webhook_server(
            loop=asyncio.get_running_loop(),
            config=server_config,
            bot_data=application.bot_data,
            reply_text_func=reply_text_func,
        )
    except OSError as error:
        print(
            f"\033[31m[Feishu webhook 启动失败]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 FEISHU_WEBHOOK_HOST/PORT 是否可绑定，或确认端口未被占用。"
        )
        raise
    application.bot_data[config.feishu_webhook_server_runtime_key] = runtime


def _stop_feishu_webhook_server_if_running(application: Application, *, config: TelegramSidecarRuntimeConfig) -> None:
    runtime = application.bot_data.pop(config.feishu_webhook_server_runtime_key, None)
    if not isinstance(runtime, FeishuWebhookServerRuntime):
        return
    stop_feishu_webhook_server(runtime)


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
        print(
            "\033[31m[WeCom webhook 配置不完整]\033[0m 缺少有效的 server config。\n"
            "\033[33m[处理建议]\033[0m 同时配置 WECOM_TOKEN/WECOM_ENCODING_AES_KEY/WECOM_RECEIVE_ID，并在启动阶段注入 webhook host/port/path。"
        )
        return
    try:
        runtime = start_wecom_webhook_server(
            loop=asyncio.get_running_loop(),
            config=server_config,
            bot_data=application.bot_data,
        )
    except OSError as error:
        print(
            f"\033[31m[WeCom webhook 启动失败]\033[0m 原因={error}\n"
            "\033[33m[处理建议]\033[0m 检查 WECOM_WEBHOOK_HOST/PORT 是否可绑定，或确认端口未被占用。"
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
        print(
            "\033[31m[personal WeChat 私聊文本服务配置无效]\033[0m bot_data 中的 personal_wechat_text_service 不是有效服务实例。\n"
            "\033[33m[处理建议]\033[0m 删除错误注入值，或改为 PersonalWeChatTextService 实例后重启服务。"
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
