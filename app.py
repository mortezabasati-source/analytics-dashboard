import sys
from pathlib import Path

# اضافه کردن پوشه src به مسیر پایتون برای شناسایی ماژول‌ها
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# ایمپورت و اجرای برنامه اصلی
import app

if __name__ == "__main__":
    app.main()