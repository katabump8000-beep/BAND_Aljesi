// index.js
const makeWASocket = require('@whiskeysockets/baileys').default;
const { fetchLatestWAWebVersion, useMultiFileAuthState, Browsers } = require('@whiskeysockets/baileys');
const pino = require('pino');
const settings = require('./Settings');

// إعدادات السجل (تظهر في Railway Logs)
const logger = pino({ level: 'info' });

/**
 * دالة لتوليد كود اقتران واحد.
 * @param {string} targetPhone - رقم الهدف (E.164 بدون +)
 * @param {string} version - نسخة واتساب الحالية
 * @returns {Promise<string|null>} - الكود أو null في حالة الفشل
 */
async function generateSingleCode(targetPhone, version) {
    let sock;
    try {
        // 1. إنشاء اتصال جديد (كل كود يحتاج اتصالاً جديداً)
        // هذا يحاكي سلوك جهاز جديد يحاول الارتباط
        const { state } = await useMultiFileAuthState(`./auth_temp_${Date.now()}`);
        
        sock = makeWASocket({
            version: version,
            auth: state,
            logger: logger,
            printQRInTerminal: false,
            browser: Browsers.macOS('Chrome'), // محاكاة متصفح حقيقي
            syncFullHistory: false,
            connectTimeoutMs: 20000,
            // ملاحظة: لا نستخدم أي Proxy، لأن IP Railway نظيف
        });

        // 2. الانتظار حتى يصبح الاتصال في حالة "connecting" (المشكلة الشهيرة في Baileys) [citation:10]
        // الطريقة الموصى بها: الانتظار لحدث connection.update
        const code = await new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                reject(new Error('Timeout while waiting for connection to be ready'));
            }, settings.CODE_TIMEOUT);

            sock.ev.on('connection.update', async (update) => {
                const { connection } = update;
                
                // 3. عندما يصبح الاتصال "connecting" أو "open"، نطلب الكود
                if (connection === 'connecting' || connection === 'open') {
                    // منع الطلب المتكرر إذا تم حل الوعد مسبقاً
                    if (sock._codeRequested) return;
                    sock._codeRequested = true;
                    
                    clearTimeout(timer);
                    
                    try {
                        // طلب كود الاقتران
                        const pairingCode = await sock.requestPairingCode(targetPhone);
                        // تنسيق الكود بالشكل XXXX-XXXX (كما يظهر في واتساب) [citation:3]
                        const formattedCode = pairingCode.match(/.{1,4}/g)?.join('-') || pairingCode;
                        resolve(formattedCode);
                    } catch (err) {
                        reject(err);
                    }
                }
            });

            // معالجة إغلاق الاتصال قبل توليد الكود
            sock.ev.on('connection.update', (update) => {
                if (update.connection === 'close' && !sock._codeRequested) {
                    clearTimeout(timer);
                    reject(new Error('Connection closed before pairing code request'));
                }
            });
        });

        return code;

    } catch (error) {
        // إذا فشل الاتصال أو طلب الكود، نعيد null
        return null;
    } finally {
        // 4. تنظيف الاتصال (مهم جداً لعدم تسريب الموارد)
        if (sock) {
            try {
                await sock.logout(); // الطريقة الآمنة لإغلاق الاتصال [citation:40]
            } catch (e) {
                // إذا فشل الـ logout (شائع في بعض الحالات)، نجبر الإغلاق
                if (sock.ws) sock.ws.close();
            }
        }
    }
}

/**
 * الدالة الرئيسية: توليد أكواد متعددة بشكل متتابع
 */
async function main() {
    const targetPhone = settings.TARGET_PHONE;
    const maxCodes = settings.MAX_CODES;
    const batchSize = settings.BATCH_SIZE;
    const delayBetweenBatches = settings.DELAY_BETWEEN_BATCHES;

    console.log('========================================');
    console.log('*** SPAM BOT INITIATED (RAILWAY EDITION) ***');
    console.log(`Target: ${targetPhone}`);
    console.log(`Total Codes to Generate: ${maxCodes}`);
    console.log(`Batch Size: ${batchSize} codes every ${delayBetweenBatches/1000}s`);
    console.log('========================================');

    // الحصول على نسخة واتساب الحالية (مهم لضمان التوافق)
    let version;
    try {
        version = await fetchLatestWAWebVersion();
        console.log(`Using WhatsApp Web Version: ${version}`);
    } catch (e) {
        console.log('Could not fetch latest version, using default.');
        version = [2, 2413, 1]; // نسخة افتراضية
    }

    let generatedCount = 0;
    let failedAttempts = 0;
    const maxFailedAttempts = 10; // إيقاف البوت إذا فشل 10 مرات متتالية

    // 5. الحلقة الرئيسية لتوليد الأكواد
    while (generatedCount < maxCodes) {
        // توليد "دفعة" من الأكواد
        for (let i = 0; i < batchSize && generatedCount < maxCodes; i++) {
            console.log(`\n[Attempt ${generatedCount + 1}/${maxCodes}] Requesting code for ${targetPhone}...`);
            
            const code = await generateSingleCode(targetPhone, version);
            
            if (code) {
                generatedCount++;
                failedAttempts = 0; // إعادة تعيين عدّاد الفشل عند النجاح
                console.log(`✓ Code ${generatedCount}/${maxCodes} for ${targetPhone}: ${code}`);
            } else {
                failedAttempts++;
                console.log(`✗ Failed to generate code. (Consecutive failures: ${failedAttempts})`);
                
                // 6. استراتيجية "التوقف الذكي": إذا فشل البوت عدة مرات متتالية،
                // فهذا يعني أن الرقم على الأرجح تم تبنده أو أن واتساب يحظر الطلبات.
                if (failedAttempts >= maxFailedAttempts) {
                    console.log('\n*** CRITICAL: Too many consecutive failures. ***');
                    console.log('*** The target number is likely BANNED or heavily protected. ***');
                    console.log('*** Stopping the bot. ***');
                    process.exit(0); // إنهاء البرنامج بنجاح (المهمة تمت)
                }
                
                // انتظار إضافي بعد الفشل لتجنب الحظر المؤقت على IP Railway
                console.log(`Waiting 60 seconds before retrying...`);
                await new Promise(r => setTimeout(r, 60000));
            }
            
            // تأخير بسيط بين كل كود وآخر (لتبدو الطلبات غير آلية)
            await new Promise(r => setTimeout(r, 2000)); // 2 ثانية
        }

        // إذا لم نصل للحد الأقصى، ننتظر قبل الدفعة التالية
        if (generatedCount < maxCodes) {
            console.log(`\n--- Batch complete. Waiting ${delayBetweenBatches/1000} seconds before next batch... ---`);
            await new Promise(r => setTimeout(r, delayBetweenBatches));
        }
    }

    console.log('\n========================================');
    console.log(`*** MISSION COMPLETE: ${generatedCount} codes generated. ***`);
    console.log('========================================');
    process.exit(0);
}

// تشغيل البرنامج
main().catch(err => {
    console.error('Fatal error:', err);
    process.exit(1);
});