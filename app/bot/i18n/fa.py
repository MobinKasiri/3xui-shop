"""
All user-facing Persian strings in one place.
No string may appear in handlers directly — always import from here.

Custom emoji: app/bot/i18n/emoji_registry.json + emoji_ids.json
Run: python scripts/sync_emoji_packs.py
"""
from app.bot.utils.emoji import i

# ─── Common ──────────────────────────────────────────────────────────────────

BACK = "بازگشت"
BACK_DOUBLE = "بازگشت"
BACK_TO_MENU = "بازگشت به منوی اصلی"
HOME = "منوی اصلی"
CANCEL = "لغو"
CONFIRM = "تایید"
REJECT = "رد کردن"
CLOSE = f"{i('close')} بستن"
REFRESH = f"{i('refresh')} بروزرسانی"
COMING_SOON = f"{i('soon')} این بخش به‌زودی فعال می‌شود."

# ─── Bot profile (shown before START + in bot info) ───────────────────────────

# Telegram limit: 512 chars — plain Unicode in profile (no custom emoji API)
BOT_DESCRIPTION = (
    "ان‌سی‌ وی‌پی‌ان انتخابی حرفه‌ای برای دسترسی آزاد و پایدار به اینترنت ⚡\n\n"
    "👩‍💻 پشتیبانی 24 ساعته توسط تیم مجرب\n"
    "🚀 تحویل آنی سرویس پس از تأیید پرداخت\n"
    "💳 امکان پرداخت ریالی (کارت‌به‌کارت)\n"
    "💰 قیمت‌گذاری شفاف و رقابتی\n"
    "📊 مدیریت مصرف و سرعت فوق‌العاده\n"
    "🌐 ارتباط پایدار و بدون قطعی\n\n"
    "برای شروع کافیست /start را ارسال کنید و به اینترنت بدون محدودیت دسترسی داشته باشید."
)

BOT_SHORT_DESCRIPTION = (
    "ان‌سی‌ وی‌پی‌ان پرسرعت — تحویل آنی | پرداخت ریالی | پشتیبانی 24/7 🚀"
)

# ─── Welcome & Main Menu ─────────────────────────────────────────────────────

CHANNEL_GATE_TEXT = (
    f"کاربر عزیز {i('rose')}\n\n"
    f"برای استفاده از ربات لطفاً با دکمه‌های زیر در کانال‌های ما عضو شوید {i('fire')}\n\n"
    f"بعد از عضو شدن روی دکمه «{i('confirm')} عضو شدم» کلیک کنید."
)
CHANNEL_GATE_NOT_JOINED = (
    f"{i('error')} هنوز در همه کانال‌ها عضو نشده‌اید.\n\n"
    "کانال‌های باقی‌مانده:\n{channels}"
)

WELCOME = (
    f"{i('wave')} خوش اومدی به <b>ان‌سی‌وی‌پی‌ان</b>!\n\n"
    f"{i('globe')} اینجا می‌تونی VPN پرسرعت و پایدار بگیری\n"
    f"اتصال سریع و بدون قطعی، مجهز به پروتکل‌های مدرن {i('bolt')}\n"
    f"پشتیبانی 24 ساعته در کنارت هستیم {i('handshake')}\n\n"
    "از گزینه‌های زیر یکی رو انتخاب کن:"
)

# Button labels — icon via icon_custom_emoji_id in keyboards
MAIN_BTN_BUY = "خرید سرویس"
MAIN_BTN_CONFIGS = "مدیریت کانفیگ‌ها"
MAIN_BTN_BALANCE = "افزایش موجودی"
MAIN_BTN_ACCOUNT = "حساب کاربری"
MAIN_BTN_FREE = "کانفیگ رایگان"
MAIN_BTN_SUPPORT = "ارتباط با پشتیبانی"
MAIN_BTN_APPS = "دریافت اپلیکیشن‌ها"
MAIN_BTN_ADMIN = "پنل مدیریت"

CMD_START = "منوی اصلی"
CMD_BUY = "خرید سرویس"
CMD_CONFIGS = "مدیریت کانفیگ‌ها"
CMD_TOPUP = "افزایش موجودی"

# ─── Errors ──────────────────────────────────────────────────────────────────

ERRORS = {
    "general": f"{i('error')} خطایی رخ داد. لطفاً مجدداً تلاش کنید.",
    "api_error": f"{i('warning')} خطا در ارتباط با سرور. لطفاً چند لحظه دیگر تلاش کنید.",
    "config_create_failed": (
        f"{i('error')} خطا در ایجاد سرویس. تیم پشتیبانی در حال بررسی است."
    ),
    "vpn_unavailable": (
        f"{i('error')} اتصال به پنل VPN برقرار نیست.\n"
        "لطفاً چند دقیقه بعد دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
    ),
    "insufficient_balance": (
        f"{i('wallet')} موجودی کافی نیست!\n\n"
        "موجودی فعلی: <b>{balance}</b> تومان\n"
        "مبلغ مورد نیاز: <b>{required}</b> تومان\n"
        "کمبود: <b>{shortage}</b> تومان\n\n"
        "برای افزایش موجودی از منوی اصلی اقدام کنید."
    ),
    "insufficient_balance_alert": (
        "💰 موجودی کافی نیست!\n\n"
        "موجودی فعلی: {balance} تومان\n"
        "مبلغ مورد نیاز: {required} تومان\n"
        "کمبود: {shortage} تومان\n\n"
        "برای افزایش موجودی از منوی اصلی اقدام کنید."
    ),
    "service_name_taken": (
        f"{i('error')} این نام قبلاً استفاده شده است.\n"
        "نام دیگری انتخاب کنید."
    ),
    "service_name_invalid": (
        f"{i('error')} نام نامعتبر است!\n"
        "فقط حروف کوچک انگلیسی (a-z) و اعداد (0-9) مجاز است.\n"
        "طول نام باید بین 3 تا 30 کاراکتر باشد.\n\n"
        "دوباره تلاش کنید:"
    ),
    "invalid_discount": f"{i('error')} کد تخفیف نامعتبر یا منقضی شده است.",
    "discount_used": f"{i('error')} شما قبلاً از این کد تخفیف استفاده کرده‌اید.",
    "banned": (
        f"{i('ban')} دسترسی شما محدود شده است.\n"
        "برای پیگیری با پشتیبانی تماس بگیرید."
    ),
    "admin_only": f"{i('ban')} این بخش فقط برای مدیران قابل دسترسی است.",
    "not_found": f"{i('error')} مورد درخواستی یافت نشد.",
    "config_not_found": f"{i('error')} سرویس مورد نظر یافت نشد.",
    "quantity_invalid": (
        f"{i('error')} تعداد نامعتبر است. عددی بین {{min}} تا {{max}} وارد کنید."
    ),
    "amount_invalid": f"{i('error')} مبلغ نامعتبر است. عدد صحیح وارد کنید.",
    "amount_min": f"{i('error')} حداقل مبلغ {{min}} تومان است.",
    "amount_max": f"{i('error')} حداکثر مبلغ {{max}} تومان است.",
}

# ─── Buy: type ───────────────────────────────────────────────────────────────

BUY_TYPE_HEADER = f"{i('cart')} برای خرید سرویس لطفاً یکی از دسته‌بندی‌های زیر را انتخاب کنید."

BUY_VIP_BTN = "سرویس VIP چند لوکیشن"

VIP_TIER_NAME_DEFAULT = "سرویس VIP چند لوکیشن"
VIP_PLANS_TABLE_SUBTITLE_DEFAULT = "یک اشتراک — همه سرورها فعال می‌شوند:"
VIP_PLANS_TABLE_LOCATIONS_DEFAULT = "🇩🇪 آلمان · 🇵🇱 لهستان · 🇸🇬 سنگاپور · 🇺🇸 آمریکا"
VIP_PLANS_TABLE_FOOTER_DEFAULT = f"{i('down')} پلن مورد نظر را انتخاب کنید:"

VIP_PLANS_TABLE_HEADER = (
    f"{i('globe')} <b>سرویس VIP چند لوکیشن</b>\n\n"
    "یک اشتراک — همه سرورها فعال می‌شوند:\n"
    "🇩🇪 آلمان · 🇵🇱 لهستان · 🇸🇬 سنگاپور · 🇺🇸 آمریکا"
)
VIP_PLANS_TABLE_ROW = "  {emoji}{gb} گیگ · {days} روز · <b>{price}</b> تومان{badge}"
VIP_PLANS_TABLE_FOOTER = f"\n{i('down')} پلن مورد نظر را انتخاب کنید:"

VIP_PLAN_BTN = "{lead}{gb} گیگ · {price} تومان{badge}"

# ─── Buy: quantity ───────────────────────────────────────────────────────────

QUANTITY_PROMPT = (
    f"{i('package')} <b>تعداد سرویس</b>\n\n"
    f"{i('note')} پلن انتخابی: {{gb}} گیگ | {{days}} روزه | {{price}} ت\n"
    f"{i('wallet')} هر عدد: <b>{{price}} تومان</b>\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "چند تا می‌خوای؟\n"
    "بین <b>1</b> تا <b>{max}</b> عدد رو تایپ کن و بفرست:"
)

# ─── Buy: service name ───────────────────────────────────────────────────────

SERVICE_NAME_PROMPT = (
    f"{i('tag')} <b>نام سرویس</b>\n\n"
    "یه اسم دلخواه برای سرویست بنویس.\n"
    "فقط حروف انگلیسی کوچک و عدد مجازه.\n\n"
    f"{i('edit')} نمونه: <code>ali</code> یا <code>myVPN1</code>\n\n"
    "یا «نام رندوم» رو بزن تا خودمون یه اسم بسازیم."
)
SERVICE_NAME_RANDOM_BTN = "نام رندوم"

SERVICE_NAME_MULTI_PROMPT = (
    f"{i('tag')} <b>نام سرویس‌ها</b>\n\n"
    "{n} سرویس انتخاب کردی.\n"
    "یه نام پایه بنویس — شماره به انتهاش اضافه می‌شه.\n\n"
    f"{i('edit')} نمونه: <code>vpn</code> ← vpn-1، vpn-2 …\n\n"
    "یا «نام رندوم» رو بزن."
)

# ─── Buy: discount ───────────────────────────────────────────────────────────

DISCOUNT_PROMPT = (
    f"{i('ticket')} <b>کد تخفیف ویژه</b>\n\n"
    f"{i('package')} تعداد: <b>{{quantity}}</b> عدد\n"
    f"{i('money')} مبلغ قابل پرداخت: <b>{{amount}}</b> تومان\n\n"
    f"پیش از پرداخت، اگر کد تخفیف اختصاصی دارید کد تخفیف را وارد کرده {i('key')}\n"
    f"و از مزایای ویژه آن بهره‌مند شوید {i('gift')}\n\n"
    f"{i('note')} لطفاً کد تخفیف خود را تایپ کرده و ارسال کنید:"
)
DISCOUNT_SKIP_BTN = "خیر، ادامه"

DISCOUNT_APPLIED = (
    f"{i('confirm')} کد تخفیف اعمال شد!\n"
    f"{i('wallet')} تخفیف: <b>{{discount}}</b> تومان\n"
    f"{i('money')} مبلغ جدید: <b>{{new_amount}}</b> تومان"
)

# ─── Buy: payment method ─────────────────────────────────────────────────────

PAYMENT_METHOD_HEADER = (
    f"{i('refresh')} تحویل آنی | {{gb}} گیگ | {{days}} روزه | {{unit_price}} ت\n"
    f"{i('package')} تعداد: <b>{{quantity}}</b> عدد\n"
    f"{i('money')} مبلغ قابل پرداخت: <b>{{amount}}</b> تومان\n\n"
    "روش پرداخت را انتخاب کنید:\n"
    "<i>موجودی کیف پول شما روی دکمه نمایش داده می‌شود.</i>"
)
PAY_WALLET_BTN = "پرداخت از موجودی ({balance} ت)"
PAY_CARD_BTN = "کارت‌به‌کارت"

# ─── Buy: card payment ───────────────────────────────────────────────────────

CARD_PAYMENT = (
    f"{i('card')} <b>کارت به کارت</b>\n\n"
    f"{i('bank')} {{bank}}\n"
    f"{i('user')} {{owner}}\n"
    f"{i('card')} <code>{{card}}</code>\n\n"
    "──────────────────\n\n"
    f"{i('money')} مبلغ قابل پرداخت\n"
    "<b>{amount}</b> تومان\n\n"
    "──────────────────\n\n"
    f"{i('warning')} حتماً مبلغ را به همین مقدار واریز نمایید.\n"
    "در صورت واریز مبلغ غیر دقیق، مسئولیت تایید نشدن\n"
    "رسید بر عهده خود شما خواهد بود.\n\n"
    f"{i('camera')} پس از واریز، تصویر رسید را ارسال کنید.\n\n"
    f"{i('down')} برای کپی مبلغ یا شماره کارت، دکمه‌های زیر را بزنید."
)
COPY_RIAL_BTN = "مبلغ ریال"
COPY_TOMAN_BTN = "مبلغ تومان"
COPY_CARD_BTN = "شماره کارت"
CANCEL_PLAIN = "لغو"

RECEIPT_RECEIVED = (
    f"{i('confirm')} رسید پرداخت دریافت شد!\n\n"
    f"{i('pending')} در حال بررسی توسط تیم پشتیبانی…\n"
    "معمولاً در کمتر از 30 دقیقه تایید می‌شود.\n\n"
    "پس از تایید، سرویس شما فعال و اطلاع‌رسانی می‌شود."
)
RECEIPT_PROMPT = f"{i('camera')} لطفاً تصویر رسید پرداخت را ارسال کنید."

# ─── Buy: success ────────────────────────────────────────────────────────────

PURCHASE_SUCCESS_ONE = (
    f"{i('party')} <b>سرویس شما فعال شد!</b>\n\n"
    f"{i('tag')} نام سرویس: <b>{{name}}</b>\n"
    f"{i('package')} پلن: {{plan_name}} — {{gb}} گیگ | {{days}} روز\n"
    f"{i('clock')} وضعیت: {{expiry}}\n\n"
    f"{i('link')} <b>لینک اشتراک (همه لوکیشن‌ها):</b>\n"
    "<code>{sub_url}</code>\n\n"
    f"{i('info')} لینک را در برنامه وارد کنید تا همه لوکیشن‌ها و سرورها به طور خودکار اضافه شوند."
)
PURCHASE_SUCCESS_BULK = (
    f"{i('party')} <b>{{n}} سرویس با موفقیت ایجاد شد!</b>\n\n"
    "{lines}\n\n"
    "از منوی اصلی → «مدیریت کانفیگ‌ها» جزئیات هر سرویس را ببینید."
)
PURCHASE_LINE = f"{i('tag')} <b>{{name}}</b> — {{sub_url}}"
PURCHASE_REJECTED = (
    f"{i('error')} <b>پرداخت شما رد شد.</b>\n\n"
    "{reason}\n\n"
    "در صورت نیاز با پشتیبانی تماس بگیرید."
)

# ─── Admin payment forward ───────────────────────────────────────────────────

ADMIN_PAYMENT_FWD = (
    f"{i('card')} <b>درخواست پرداخت جدید</b>  #TXN-{{tx_id}}\n\n"
    f"{i('user')} کاربر: {{name}} (@{{username}})\n"
    f"{i('id_badge')} آیدی: <code>{{tg_id}}</code>\n"
    f"{i('package')} پلن: {{plan_name}}\n"
    f"🔢 تعداد: {{quantity}}\n"
    f"{i('tag')} نام سرویس: <b>{{service_name}}</b>\n"
    f"{i('wallet')} مبلغ: <b>{{amount}}</b> تومان\n"
    f"{i('ticket')} تخفیف: {{discount}}\n"
    f"{i('clock')} زمان: {{datetime}}"
)
ADMIN_WALLET_FWD = (
    f"{i('wallet')} <b>درخواست شارژ کیف پول</b>  #TXN-{{tx_id}}\n\n"
    f"{i('user')} کاربر: {{name}} (@{{username}})\n"
    f"{i('id_badge')} آیدی: <code>{{tg_id}}</code>\n"
    f"{i('cash')} مبلغ: <b>{{amount}}</b> تومان\n"
    f"{i('clock')} زمان: {{datetime}}"
)
ADMIN_APPROVE_BTN = "تایید و ایجاد سرویس"
ADMIN_APPROVE_WALLET_BTN = "تایید شارژ"
ADMIN_REJECT_BTN = "رد کردن"

# ─── Manage Configs ──────────────────────────────────────────────────────────

CONFIGS_LIST_HEADER = (
    f"{i('chart')} <b>مدیریت کانفیگ‌ها</b>\n\n"
    "تعداد: {count}"
)
CONFIGS_LIST_EMPTY = (
    f"{i('chart')} <b>مدیریت کانفیگ‌ها</b>\n\n"
    f"{i('error')} شما هیچ سرویس فعالی ندارید.\n\n"
    "برای خرید سرویس از منوی اصلی اقدام کنید."
)
CONFIG_LIST_ROW = "… {name}"
CONFIG_LIST_ROW_EXPIRED = f"{i('sleep')} {{name}} (منقضی)"

CONFIG_DETAIL = (
    f"{i('refresh')} نام سرویس: <b>{{name}}</b>\n"
    f"{i('star')} نوع سرویس: {{plan_name}}\n"
    f"{i('battery')} حجم: <b>{{total_gb}}</b> گیگ\n"
    f"{i('clock')} مدت زمان: {{duration}}\n"
    f"{i('user')} تعداد کاربر: نامحدود\n\n"
    f"{i('key')} <b>کانفیگ اتصال:</b>\n"
    "<code>{vless}</code>\n\n"
    f"{i('link')} <b>لینک اشتراک:</b>\n"
    "<code>{sub_url}</code>"
)

CONFIG_BTN_USAGE = "وضعیت و راهنمای سرویس"
CONFIG_BTN_GET_CONFIGS = "دریافت کانفیگ‌ها"
CONFIG_BTN_GET_SUB = "دریافت اشتراک"
CONFIG_BTN_DISABLE = "غیرفعال‌سازی موقت"
CONFIG_BTN_ENABLE = "فعال‌سازی"
CONFIG_BTN_DELETE = "حذف کانفیگ"
CONFIG_BTN_RESET_SUB = "تغییر لینک ساب"
CONFIG_BTN_QR = "QR ساب"

CONFIG_INFO_TRAFFIC = f"{i('battery')} {{used}} از {{total}} گیگ"
CONFIG_INFO_UNLIMITED = f"{i('infinity')} نامحدود"

CONFIG_STATUS_TEXT = (
    f"{i('chart')} <b>وضعیت سرویس: {{name}}</b>\n\n"
    f"{i('up')} مصرف حجم:\n"
    "<code>[{bar}] {used_gb} از {total_gb} گیگ ({pct}٪)</code>\n\n"
    f"{i('clock')} وضعیت انقضا: <b>{{expiry}}</b>\n"
    f"{i('pending')} روزهای باقیمانده: <b>{{days}}</b>\n\n"
    f"{i('up')} آپلود: {{up}}\n"
    f"{i('down')} دانلود: {{down}}"
)

CONFIG_GET_CONFIGS_TEXT = (
    f"{i('copy')} <b>کانفیگ‌های سرویس: {{name}}</b>\n"
    "<i>همه لوکیشن‌ها — پس از import اشتراک، همه را خواهید داشت</i>\n\n"
    "{links}"
)
CONFIG_GET_CONFIGS_EMPTY = (
    f"{i('error')} کانفیگی از پنل دریافت نشد. از لینک اشتراک استفاده کنید."
)
CONFIG_GET_SUB_TEXT = (
    f"{i('key')} <b>لینک اشتراک سرویس: {{name}}</b>\n\n"
    "<code>{url}</code>\n\n"
    "این لینک را در اپ خود وارد کنید.\n"
    f"{i('warning')} لینک اشتراک خصوصی است — با دیگران به اشتراک نگذارید."
)
DELAYED_START_FMT = f"{i('pending')} هنوز شروع نشده — شروع {{n}} روز پس از اولین اتصال"
CONFIG_NOT_STARTED = f"{i('pending')} هنوز شروع نشده"

CONFIG_DISABLED = f"{i('pause')} سرویس موقتاً غیرفعال شد."
CONFIG_ENABLED = f"{i('play')} سرویس مجدداً فعال شد."
CONFIG_RESET_SUB_DONE = (
    f"{i('refresh')} لینک اشتراک تغییر کرد:\n"
    "<code>{url}</code>"
)
CONFIG_QR_CAPTION = f"{i('phone')} QR کد سرویس: <b>{{name}}</b>"

CONFIG_DELETE_CONFIRM = (
    f"{i('warning')} <b>آیا مطمئن هستید؟</b>\n\n"
    "سرویس «<b>{name}</b>» برای همیشه حذف خواهد شد.\n"
    "این عمل قابل بازگشت نیست."
)
CONFIG_DELETE_YES = "بله، حذف شود"
CONFIG_DELETE_NO = "خیر، بازگشت"
CONFIG_DELETED = (
    f"{i('trash')} سرویس «{{name}}» حذف شد.\n\n"
    "اگر در v2Box هنوز کانفیگ می‌بینید، اشتراک قدیمی را از اپ حذف کنید."
)

# ─── Account / Wallet ────────────────────────────────────────────────────────

PROFILE_TEXT = (
    f"{i('user')} <b>پروفایل کاربری</b>\n\n"
    f"{i('user')} نام: <b>{{name}}</b>\n"
    f"{i('key')} نام کاربری: {{username}}\n"
    f"{i('id_badge')} آیدی: <code>{{tg_id}}</code>\n"
    f"{i('money')} موجودی: <b>{{balance}}</b> تومان"
)
WALLET_TOPUP_BTN = "افزایش موجودی"
WALLET_TX_BTN = "تراکنش‌های من"

TOPUP_AMOUNTS_HEADER = (
    f"{i('wallet')} <b>افزایش موجودی کیف پول</b>\n\n"
    "مبلغ موردنظر را انتخاب یا وارد کنید:"
)
TOPUP_CUSTOM_BTN = "مبلغ دلخواه"
TOPUP_CUSTOM_PROMPT = (
    f"{i('edit')} مبلغ مورد نظر را به تومان وارد کنید:\n"
    "(مثال: 100000)"
)

TX_LIST_HEADER = f"{i('receipt')} <b>تراکنش‌های من</b>\n"
TX_LIST_EMPTY = f"{i('receipt')} <b>تراکنش‌های من</b>\n\nهنوز تراکنشی ثبت نشده است."
TX_LIST_ROW = (
    "──────────────────\n"
    "{icon} {desc}\n"
    f"{i('wallet')} {{sign}}{{amount}} تومان\n"
    f"{i('clock')} {{date}}"
)
TX_ICON_CREDIT = i("confirm")
TX_ICON_DEBIT = i("error")
TX_ICON_PENDING = i("pending")
TX_ICON_REFERRAL = i("gift")

WALLET_CHARGED = (
    f"{i('confirm')} <b>موجودی شما با موفقیت شارژ شد!</b>\n\n"
    "موجودی جدید: <b>{balance}</b> تومان"
)

# ─── Referral / Free Config ──────────────────────────────────────────────────

REFERRAL_WITH_STATS = (
    f"{i('referral')} <b>دعوت دوستان — ان‌سی‌ وی‌پی‌ان</b>\n\n"
    "با دعوت از دوستان خود و ثبت خرید توسط آن‌ها با لینک اختصاصی‌تان:\n"
    f"{i('wallet')} <b>{{ref_bonus}} تومان</b> به کیف پول شما اضافه می‌شود\n"
    f"{i('gift')} دوستتان نیز <b>{{friend_bonus}} تومان</b> هدیه‌ی اولیه دریافت می‌کند\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{i('chart')} <b>وضعیت شما:</b>\n"
    f"{i('user')} تعداد دعوت‌شده‌ها: <b>{{count}}</b> نفر\n"
    f"{i('cart')} مجموع خریدها: <b>{{purchases}}</b> بار\n"
    f"{i('wallet')} کل پاداش دریافتی: <b>{{total_revenue}}</b> تومان\n\n"
    f"{i('link')} <b>لینک ویژه شما:</b>\n"
    "<code>{ref_link}</code>"
)
REFERRAL_NO_STATS = (
    f"{i('referral')} <b>دوستت رو دعوت کن، هر دو سود می‌برید!</b>\n\n"
    "هر بار که یه نفر با لینک تو بیاد و سرویس بخره،\n"
    f"<b>50,000 تومان</b> به کیف پولت واریز می‌شه. {i('cash')}\n\n"
    f"دوستت هم یه هدیه خوش‌آمد دریافت می‌کنه\n"
    f"تا از همون اول بتونه سرویس بگیره. {i('gift')}\n\n"
    f"{i('link')} <b>لینک دعوت اختصاصی:</b>\n"
    "<code>{ref_link}</code>"
)
REFERRAL_SHARE_BTN = "اشتراک‌گذاری لینک"
REFERRAL_POST_BTN = "متن آماده برای فوروارد"
REFERRAL_SHARE_DIALOG_TEXT = f"{i('bolt')} VPN پرسرعت — ان‌سی‌ وی‌پی‌ان"

REFERRAL_READY_POST = (
    f"<b>{i('bolt')} ان‌سی‌ وی‌پی‌ان — VPN سریع و ایمن</b>\n\n"
    f"پروتکل‌های مدرن VLESS {i('globe')}\n"
    f"پشتیبانی آنلاین {i('handshake')}\n"
    f"سازگار با تمامی دستگاه‌ها و اپراتورها {i('phone')}\n"
    f"بدون محدودیت تعداد دستگاه {i('lock')}\n\n"
    "با استفاده از لینک من عضو شو و هدیه‌ی خوش‌آمد بگیر:\n"
    "{ref_link}"
)
REFERRAL_READY_POST_HINT = f"{i('confirm')} متن آماده‌ست، می‌تونی فوروارد کنی."

# ─── Apps ────────────────────────────────────────────────────────────────────

APPS_HEADER = (
    f"{i('download')} <b>دریافت اپلیکیشن‌ها</b>\n\n"
    "سیستم‌عامل خود را انتخاب کنید:"
)
APPS_OS_BTN = {
    "android": "Android",
    "ios": "iOS",
    "windows": "Windows",
    "mac": "Mac",
    "linux": "Linux",
}
APPS_OS_HEADER = f"{i('phone')} <b>اپلیکیشن‌های {{os}}</b>\n\nبرنامه مورد نظر را انتخاب کنید:"

# ─── Support ─────────────────────────────────────────────────────────────────

SUPPORT_HEADER = (
    f"{i('support')} <b>پشتیبانی ان‌سی‌ وی‌پی‌ان</b>\n\n"
    "سوالات متداول رو اول بررسی کن —\n"
    f"پاسخ خیلی از مشکلاتت رو اونجا پیدا می‌کنی {i('down')}"
)
SUPPORT_FAQ_BTN = "سوالات متداول (FAQ)"
SUPPORT_ONLINE_BTN = "چت با پشتیبانی ↗️"

FAQ_TEXT = (
    f"{i('faq')} <b>سوالات متداول — ان‌سی‌ وی‌پی‌ان</b>\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "1️⃣ <b>آیا امکان استفاده آزمایشی وجود دارد؟</b>\n"
    "خیر، به دلایل امنیتی و پیشگیری از سوء استفاده، ما سرویس رایگان یا آزمایشی ارائه نمی‌کنیم.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "2️⃣ <b>آیا برای تعداد کاربر یا دستگاه محدودیتی تعیین شده؟</b>\n"
    "خیر، هیچ گونه محدودیتی در تعداد دستگاه یا استفاده همزمان وجود ندارد و می‌توانید روی هر تعداد دستگاه دلخواه سرویس را فعال کنید.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "3️⃣ <b>اتصال از لحاظ سرعت و پایداری چگونه است؟</b>\n"
    "سرورها دارای پهنای باند بالا هستند. البته گاهی برای تغییرات آی‌پی، ممکن است اختلال‌های کوتاه‌مدت (5 تا 15 دقیقه‌ای) رخ دهد، اما به طور کلی اتصال پایدار و مناسبی فراهم است.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "4️⃣ <b>چه برنامه‌هایی پشتیبانی می‌شوند؟</b>\n"
    "برنامه‌هایی مانند Hiddify، V2Box، V2rayNG، Streisand و سایر اپ‌ها پشتیبانی می‌شوند. لینک دانلود اپلیکیشن‌ها از منوی اصلی در دسترس است.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "5️⃣ <b>آیا بر روی تمام اپراتورهای ایران کار می‌کند؟</b>\n"
    "بله، تمام سرویس‌ها روی تمامی اپراتورهای کشور فعال هستند و هیچ محدودیت منطقه‌ای وجود ندارد.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "6️⃣ <b>حجم واقعی است یا ضریب دارد؟</b>\n"
    "حجم خریداری‌شده به همان مقدار واقعی مصرف می‌شود و هیچ ضریب یا تبدیل وجود ندارد. همچنین می‌توانید هر زمان که مایل بودید مصرف دقیق خود را با لینک ساب بررسی نمایید.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"{i('chat')} اگر سوال دیگری دارید، با پشتیبانی در تماس باشید.\n"
    "خرید تنها از ربات @{bot_username} انجام می‌شود.\n\n"
    "@{support_username}"
)

# ─── Admin dashboard ─────────────────────────────────────────────────────────

ADMIN_DASHBOARD = (
    f"{i('admin')} <b>پنل مدیریت ان‌سی‌ وی‌پی‌ان</b>\n\n"
    f"{i('chart')} <b>آمار امروز:</b>\n"
    "• کاربران جدید: {today_users}\n"
    "• درآمد امروز: {today_revenue} تومان\n\n"
    f"{i('chart')} <b>آمار کلی:</b>\n"
    "• کل کاربران: {total_users}\n"
    "• سرویس‌های فعال: {active_configs}\n"
    "• کل درآمد: {total_revenue} تومان\n\n"
    f"{i('server')} <b>وضعیت سرور:</b>\n"
    "• CPU: {cpu}٪\n"
    "• RAM: {ram}٪\n"
    "• Xray: {xray_state}"
)

ADMIN_DISCOUNT_CREATED = (
    f"{i('confirm')} <b>کد تخفیف ایجاد شد!</b>\n\n"
    f"{i('ticket')} کد: <code>{{code}}</code>\n"
    f"{i('wallet')} تخفیف: {{value}}\n"
    f"🔢 حداکثر استفاده: {{max_uses}}\n"
    f"{i('clock')} انقضا: {{expires}}"
)
ADMIN_DISCOUNT_LIST_HEADER = f"{i('ticket')} <b>کدهای تخفیف فعال</b>\n"
ADMIN_DISCOUNT_ROW = (
    "──────────────────\n"
    f"{i('ticket')} <code>{{code}}</code>\n"
    f"{i('wallet')} {{value}}\n"
    "🔢 {used}/{max_uses}\n"
    f"{i('clock')} انقضا: {{expires}}"
)
ADMIN_DISCOUNT_NOT_FOUND = f"{i('error')} کد تخفیف پیدا نشد."
ADMIN_DISCOUNT_DEACTIVATED = f"{i('trash')} کد <code>{{code}}</code> غیرفعال شد."
ADMIN_DISCOUNT_STATS = (
    f"{i('chart')} <b>آمار کد {{code}}</b>\n\n"
    "🔢 استفاده شده: {used}/{max_uses}\n"
    f"{i('clock')} ساخته شده: {{created}}\n"
    f"{i('clock')} انقضا: {{expires}}\n"
    "وضعیت: {state}"
)
ADMIN_DISCOUNT_USAGE_HELP = (
    "استفاده:\n"
    "<code>/addcode CODE PERCENT|AMOUNT USES EXPIRE_DAYS</code>\n\n"
    "مثال:\n"
    "<code>/addcode SUMMER10 10% 100 7</code>\n"
    "<code>/addcode FLAT5000 5000t 50 2</code>"
)

# ─── Notifications ───────────────────────────────────────────────────────────

NOTIF_EXPIRY_WARNING = (
    f"{i('warning')} <b>سرویس شما رو به اتمام است!</b>\n\n"
    f"{i('tag')} نام: {{name}}\n"
    f"{i('clock')} انقضا: {{expiry}} ({{days}} روز دیگر)\n"
    f"{i('chart')} حجم باقیمانده: {{remaining_gb}} گیگ\n\n"
    "برای ادامه استفاده، یک سرویس جدید تهیه کنید."
)
NOTIF_TRAFFIC_WARNING = (
    f"{i('warning')} <b>حجم سرویس شما رو به اتمام است!</b>\n\n"
    f"{i('tag')} نام: {{name}}\n"
    f"{i('chart')} مصرف: {{used_gb}} از {{total_gb}} گیگ ({{pct}}٪)\n\n"
    "برای ادامه استفاده، سرویس جدید تهیه کنید."
)
NOTIF_NEW_CONFIG_BTN = "خرید سرویس جدید"

# ─── Misc UI strings ─────────────────────────────────────────────────────────

WAIT_CREATING = f"{i('pending')} در حال ایجاد سرویس…"
WAIT_PROCESSING = f"{i('pending')} در حال پردازش…"
TX_DESC_PURCHASE = "خرید {plan_name} × {qty} ({name})"
TX_DESC_WALLET = "شارژ کیف پول"
TX_DESC_REFERRAL_RECEIVED = "هدیه معرفی دوست"
TX_DESC_REFERRAL_FRIEND = "هدیه ورود با لینک معرف"
