# گزارش نصب skillها در ZCode — ۲۰۲۶-۰۹-۰۵

هر ۱۶ skill در `C:\Users\icFixer.ir\.agents\skills\` نصب شدند (سطح کاربر — در همه workspaceها قابل استفاده). فایل‌های اصلی دست‌نخورده ماندند.

## وضعیت هر skill

| Skill | منبع | وضعیت در ZCode |
|---|---|---|
| datadog-app | Datadog | ✅ آماده (برای scaffold پروژه Datadog App) |
| ddsetup | Datadog | ⚠️ نیاز به سرور MCP دیتادوگ + کلیدهای API |
| ddconfig | Datadog | ⚠️ نیاز به سرور MCP دیتادوگ |
| ddtoolsets | Datadog | ⚠️ نیاز به سرور MCP دیتادوگ |
| ddviz | Datadog | ❌ فقط macOS (پنلvisualization با Swift) — روی ویندوز کار نمی‌کند |
| cowork-plugin-customizer | Anthropic | ⚠️ به محیط Cowork (دسکتاپ Anthropic) وابسته است — مسیرهای `mnt/.local-plugins` اینجا وجود ندارد |
| create-cowork-plugin | Anthropic | ⚠️ وابسته به Cowork — احتمالاً غیرقابل استفاده در ZCode |
| wix-app | Wix | ✅ آماده (نیاز به `@wix/cli`) |
| wix-auth | Wix | ✅ آماده |
| wix-base44-connector | Wix | ✅ آماده |
| wix-design-system | Wix | ✅ آماده |
| wix-docs | Wix | ✅ آماده (مسیر curl بدون MCP کار می‌کند؛ با MCP سریع‌تر) |
| wix-headless | Wix | ✅ آماده (فیلد `allowed-tools` مخصوص Claude است و در ZCode نادیده گرفته می‌شود — بی‌ضرر) |
| wix-manage | Wix | ✅ آماده (نیاز به API key یا OAuth ویکس) |
| wix-replatform | Wix | ✅ نصب شد؛ `name` از `replatform` به `wix-replatform` اصلاح شد تا با نام پوشه بخواند |
| wix-vibe-headless | Wix | ✅ آماده (بدون وابستگی) |

## راه‌اندازی سرور MCP (اختیاری — فقط برای Datadog و بخشی از Wix)

### Datadog
نیازمند متغیرهای محیطی `DD_API_KEY`، `DD_APPLICATION_KEY` و `DD_MCP_DOMAIN` (مثل `api.datadoghq.com`). تا وقتی این‌ها تنظیم نشوند سرور وصل نمی‌شود — پس فعلاً اضافه‌اش نکردم.

وقتی کلیدها آماده بود، این را به `C:\Users\icFixer.ir\.agents\mcp.json` اضافه کنید (فایل `.agents/mcp.json` fallback رسمی ZCode است و همین فرمت Claude را می‌خواند):

```json
{
  "mcpServers": {
    "datadog": {
      "type": "http",
      "url": "https://api.datadoghq.com/v1/mcp?referrer_ide=claude-code-plugin&plugin_version=0.7.17",
      "headers": {
        "DD_API_KEY": "<کلید شما>",
        "DD_APPLICATION_KEY": "<کلید شما>",
        "X-Datadog-MCP-Toolsets": ""
      }
    }
  }
}
```

### Wix
بدون کلید کار می‌کند (احراز هویت هنگام اولین اتصال انجام می‌شود). همان فایل، کنار datadog:

```json
{
  "mcpServers": {
    "wix-mcp": {
      "type": "http",
      "url": "https://mcp.wix.com/mcp"
    }
  }
}
```

> جایگزین: می‌توانید MCP را در `C:\Users\icFixer.ir\.zcode\cli\config.json` زیر کلید `mcp.servers` بگذارید (فرمت تو در تو). هر دو راه معتبرند.

## چیزهایی که عمداً نصب نشدند
- **hooks دیتادوگ** (`New folder/hooks/hooks.json`) — hookها در ZCode plugin-scoped هستند و به‌صورت skill منتقل نمی‌شوند؛ در صورت نیاز جداگانه باید پیکربندی شوند.
- **viz/ (پنل Swift)** — مخصوص macOS.

## تأیید نصب
بعد از باز کردن session جدید، skillها باید در **Settings → Skills** ظاهر شوند. برای تست سریع: در یک گفتگوی جدید بپرسید «کامپوننت WDS برای مودال چیست» — باید skill `wix-design-system` فعال شود.
