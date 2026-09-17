// Settings.js
// ⚠️ تحذير: هذا الملف لا يجب رفعه إلى GitHub لأنه يحتوي على بيانات حساسة.
// على Railway: أضف هذه المتغيرات في لوحة التحكم (Variables) بدلاً من رفع الملف.

module.exports = {
    // رقم الهدف (بدون + أو مسافات)
    TARGET_PHONE: process.env.TARGET_PHONE || "201124542298",
    
    // إجمالي عدد الأكواد المطلوب توليدها (الحد الأقصى 500)
    MAX_CODES: parseInt(process.env.MAX_CODES) || 500,
    
    // عدد الأكواد التي يتم توليدها في "دفعة" واحدة قبل الانتظار
    BATCH_SIZE: parseInt(process.env.BATCH_SIZE) || 5,
    
    // الوقت (بالمللي ثانية) الذي ينتظره البوت بين كل دفعة وأخرى
    DELAY_BETWEEN_BATCHES: parseInt(process.env.DELAY_BETWEEN_BATCHES) || 30000, // 30 ثانية
    
    // أقصى وقت انتظار (بالملي ثانية) لتوليد الكود الواحد قبل اعتباره فاشلاً
    CODE_TIMEOUT: parseInt(process.env.CODE_TIMEOUT) || 15000, // 15 ثانية
};