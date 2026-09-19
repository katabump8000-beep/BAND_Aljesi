import time

def check_signal_and_trade(api, symbol="EURUSD_otc", amount=1):
    """
    يفحص الشموع الحالية، وإذا تحققت الشروط يدخل صفقة تلقائياً
    """
    try:
        # جلب أحدث الشموع بخط زمني 60 ثانية (دقيقة واحدة)
        candles = api.get_candles(symbol, 60, 5)
        if not candles or len(candles) < 4:
            return None, "تعذر جلب بيانات الشموع"

        # فحص الشموع المكتملة السابقة (3 شموع)
        # نحسب اتجاه الشمعة (صعود أو هبوط) بناءً على سعر الفتح وإغلاق الشمعة
        c1 = candles[-4]
        c2 = candles[-3]
        c3 = candles[-2]

        is_c1_green = c1['close'] > c1['open']
        is_c2_green = c2['close'] > c2['open']
        is_c3_green = c3['close'] > c3['open']

        is_c1_red = c1['close'] < c1['open']
        is_c2_red = c2['close'] < c2['open']
        is_c3_red = c3['close'] < c3['open']

        action = None
        # شرط الصعود: 3 شموع خضراء متتالية -> شراء (call)
        if is_c1_green and is_c2_green and is_c3_green:
            action = "call"
        # شرط الهبوط: 3 شموع حمراء متتالية -> بيع (put)
        elif is_c1_red and is_c2_red and is_c3_red:
            action = "put"

        if action:
            # انتظار حتى التوقيت المناسب (قبل إغلاق الشمعة بـ 22 ثانية)
            current_time = time.time()
            seconds_in_minute = int(current_time) % 60
            
            # الشمعة تغلق عند الثانية 60، والدخول يكون عند الثانية 38 (60 - 22 = 38)
            if seconds_in_minute < 38:
                wait_time = 38 - seconds_in_minute
                time.sleep(wait_time)

            # تنفيذ الصفقة لمدة 60 ثانية
            status, trade_info = api.buy(amount, symbol, action, 60)
            if status:
                return action, f"تم تنفيذ صفقة {action.upper()} بمبلغ ${amount} على {symbol}"
            else:
                return None, "فشل في تنفيذ الصفقة على المنصة"

        return None, "لا توجد إشارة حالياً"

    except Exception as e:
        return None, f"خطأ في تحليل الاستراتيجية: {str(e)}"
