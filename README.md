# Rocket League Discord Webhook News

هذا المشروع **ليس Discord Bot**.

يستخدم **Discord Incoming Webhook** فقط لإرسال أخبار Rocket League إلى روم Discord، بينما GitHub Actions هو الذي يشغل جامع الأخبار كل 15 دقيقة.

## المزايا

- لا يحتاج Bot User.
- لا يحتاج Discord Bot Token.
- لا يحتاج جهازك شغالاً.
- لا يحتاج سيرفر VPS.
- يعمل من GitHub Actions.
- يركز على Rocket League فقط.
- يجمع أخبار RLCS والبطولات واللاعبين والفرق والمنظمات والانتقالات والتحديثات.
- يمنع تكرار الخبر باستخدام `data/sent.json`.
- يرسل الأخبار كـ Discord Embeds.

## 1. إنشاء Webhook في Discord

في الروم الذي تريد استقبال الأخبار فيه:

`Edit Channel > Integrations > Webhooks > New Webhook`

سمّه مثلاً:

`GGNews Rocket League`

ثم:

`Copy Webhook URL`

لا تشارك الرابط مع أحد؛ أي شخص يملكه يستطيع الإرسال إلى الروم.

## 2. GitHub Secret

في Repository:

`Settings > Secrets and variables > Actions`

ثم:

`New repository secret`

الاسم:

`DISCORD_WEBHOOK_URL`

والقيمة:

رابط الـWebhook الذي نسخته من Discord.

## 3. GitHub Actions

ارفع المشروع كما هو.

ثم:

`Actions > Rocket League News Webhook > Run workflow`

بعد التشغيل سيبدأ النشر.

وبعد ذلك سيعمل تلقائياً كل 15 دقيقة.

## 4. منع التكرار

الروابط التي تم إرسالها تحفظ في:

`data/sent.json`

ويقوم GitHub Actions بعمل commit تلقائي لتحديث الملف.

## 5. ملاحظة

Google News RSS مستخدم هنا كطبقة تجميع مجانية. البوت لا يعيد نشر نص المقال كاملاً؛ بل يرسل عنوان الخبر ووصفاً مختصراً ورابط المصدر.

## التطوير القادم

يمكن تحويل هذا إلى نظام GGNews أكثر احترافية بإضافة:

- تصنيف تلقائي: لاعب / فريق / بطولة / انتقال / تحديث.
- ترجمة وصياغة عربية.
- فلترة للأخبار المهمة.
- تنبيه Breaking News.
- مصادر Rocket League متخصصة أكثر.
- قنوات Discord مختلفة حسب التصنيف.
- صورة الخبر داخل Embed.
- نشر صياغة جاهزة بأسلوب GGNews.
