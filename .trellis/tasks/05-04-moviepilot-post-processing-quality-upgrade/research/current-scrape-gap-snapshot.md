# Current Scrape Gap Snapshot — Akron / 爱的进行时

Captured: 2026-05-04

## Real sample

- Task hash: `b49089c888d789d96a989acd709e7437a234c102`
- TMDB id: `361018`
- Confirmed title: `爱的进行时`
- Current media file:
  - `/data/library/movies/Akron DDP2 H NZMA E264.mkv`

## What is already proven

- Download completion observation works
- Auto import works
- Hardlink import works
- Metadata scrape step runs and writes artifacts
- Subtitle translation now produces `.zh.srt`
- Refresh succeeds

## Current quality gaps

### Directory / naming

- Current output is still flat under `/data/library/movies/`
- File name is still release-style:
  - `Akron DDP2 H NZMA E264.mkv`

### metadata.json

Current shape is still minimal:

- task_ref / task_id / task_hash / target_path
- tmdb:
  - id
  - title
  - original_title
  - year
  - media_type
- fanart:
  - poster_url
  - backdrop_url
- subtitle_translation.trusted_name_map

Missing:

- overview
- genres
- rating / vote stats
- studios / countries
- cast list

### nfo

Current NFO only contains:

- title
- originaltitle
- year
- tmdbid
- uniqueid

No:

- plot
- thumb/fanart on this sample
- cast list

### Images

For this real Akron sample:

- no `*-poster.*` artifact
- no `*-backdrop.*` artifact
- metadata shows empty poster/backdrop URLs

### Cast / actor truth

Current data only proves subtitle-facing trusted-name guidance.

Example:

- `Edmund Donovan -> 埃德蒙·多诺万`

This is not yet a library-facing cast model.

