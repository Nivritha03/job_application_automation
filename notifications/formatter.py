def escape_markdown(text: str) -> str:
    if not text:
        return ""
    # Telegram MarkdownV2 requires escaping the following characters:
    # '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    escaped = ""
    for char in str(text):
        if char in escape_chars:
            escaped += "\\" + char
        else:
            escaped += char
    return escaped

def format_pipeline_start(time_str: str, platforms: list, keywords: list, location: str, dry_run: bool) -> str:
    platforms_str = escape_markdown(", ".join(platforms))
    keywords_str = escape_markdown(", ".join(keywords))
    loc = escape_markdown(location or "India")
    
    return (
        f"🚀 *AI Job Agent Started*\n\n"
        f"🕒 *Time:*\n{escape_markdown(time_str)}\n\n"
        f"🏢 *Platform:*\n{platforms_str}\n\n"
        f"🔑 *Keywords:*\n{keywords_str}\n\n"
        f"🌍 *Location:*\n{loc}\n\n"
        f"🧪 *Dry Run:*\n{escape_markdown(str(dry_run))}"
    )

def format_job_found(company: str, role: str, platform: str, location: str) -> str:
    return (
        f"🔍 *New Job Found*\n\n"
        f"🏢 *Company:*\n{escape_markdown(company)}\n\n"
        f"💼 *Role:*\n{escape_markdown(role)}\n\n"
        f"🌍 *Platform:*\n{escape_markdown(platform)}\n\n"
        f"📍 *Location:*\n{escape_markdown(location)}"
    )

def format_job_matched(score: int, resume: str, company: str, role: str) -> str:
    return (
        f"📈 *Job Matched*\n\n"
        f"📊 *Score:*\n{escape_markdown(str(score))}\n\n"
        f"📄 *Resume:*\n{escape_markdown(resume)}\n\n"
        f"🏢 *Company:*\n{escape_markdown(company)}\n\n"
        f"💼 *Role:*\n{escape_markdown(role)}"
    )

def format_apply_success(company: str, role: str, platform: str, location: str, resume: str, time_str: str, url: str, score: int, app_id: str = None) -> str:
    app_id_str = escape_markdown(app_id or "N/A")
    # Escape job link inside markdown inline links
    url_str = escape_markdown(url)
    return (
        f"🎉 *Application Submitted Successfully*\n\n"
        f"🏢 *Company:*\n{escape_markdown(company)}\n\n"
        f"💼 *Role:*\n{escape_markdown(role)}\n\n"
        f"🌍 *Platform:*\n{escape_markdown(platform)}\n\n"
        f"📍 *Location:*\n{escape_markdown(location)}\n\n"
        f"📄 *Resume:*\n{escape_markdown(resume)}\n\n"
        f"🕒 *Time:*\n{escape_markdown(time_str)}\n\n"
        f"🔗 *Application URL:*\n[Job Link]({url_str})\n\n"
        f"📈 *Match Score:*\n{escape_markdown(str(score))}\n\n"
        f"🆔 *Application ID:*\n{app_id_str}"
    )

def format_apply_failed(company: str, role: str, reason: str) -> str:
    return (
        f"❌ *Application Failed*\n\n"
        f"🏢 *Company:*\n{escape_markdown(company)}\n\n"
        f"💼 *Role:*\n{escape_markdown(role)}\n\n"
        f"⚠️ *Reason:*\n{escape_markdown(reason)}"
    )

def format_retry_scheduled(company: str, reason: str, retry_after_str: str, attempt: int) -> str:
    return (
        f"⏳ *Retry Scheduled*\n\n"
        f"🏢 *Company:*\n{escape_markdown(company)}\n\n"
        f"⚠️ *Reason:*\n{escape_markdown(reason)}\n\n"
        f"🕒 *Retry After:*\n{escape_markdown(retry_after_str)}\n\n"
        f"🔄 *Next Attempt:*\n{escape_markdown(str(attempt))}"
    )

def format_daily_summary(stats: dict) -> str:
    top_str = ""
    for k, v in stats.get("top_companies", {}).items():
        top_str += f"\\- {escape_markdown(k)}: {escape_markdown(str(v))}\n"
    if not top_str:
        top_str = "None"
        
    return (
        f"📊 *Daily Summary*\n\n"
        f"🔍 *Jobs Found:* {escape_markdown(str(stats.get('found', 0)))}\n"
        f"⚙️ *Jobs Parsed:* {escape_markdown(str(stats.get('parsed', 0)))}\n"
        f"🎯 *Matched:* {escape_markdown(str(stats.get('matched', 0)))}\n"
        f"✅ *Applied:* {escape_markdown(str(stats.get('applied', 0)))}\n"
        f"⏭️ *Skipped:* {escape_markdown(str(stats.get('skipped', 0)))}\n"
        f"❌ *Failed:* {escape_markdown(str(stats.get('failed', 0)))}\n"
        f"👥 *Duplicates:* {escape_markdown(str(stats.get('duplicates', 0)))}\n\n"
        f"🏢 *Top Companies:*\n{top_str}\n"
        f"⏱️ *Average Runtime:* {escape_markdown(str(stats.get('avg_runtime', 0)))} min\n"
        f"📈 *Average Match Score:* {escape_markdown(str(stats.get('avg_score', 0)))}\n"
        f"🏆 *Total Success Rate:* {escape_markdown(str(stats.get('success_rate', 0)))}%"
    )
