FROM python:3.10-slim

WORKDIR /app

# کپی requirements و نصب پکیج‌ها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی کل پروژه
COPY . .

# تنظیمات پورت Cloud Run
ENV PORT=8080
EXPOSE 8080

# اجرای مستقیم app.py از داخل پوشه src
CMD ["streamlit", "run", "src/app.py", "--server.port=8080", "--server.address=0.0.0.0", "--server.headless=true"]