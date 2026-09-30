import sqlite3
import random

DB_NAME = "ebook_store.db"

def init():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ดึงโครงสร้างจาก schema.sql และปรับให้เข้ากับ SQLite
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema_sql = f.read()
    schema_sql = schema_sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
    schema_sql = schema_sql.replace("BOOLEAN", "INTEGER")
    schema_sql = schema_sql.replace("TRUE", "1").replace("FALSE", "0")
    
    cursor.executescript(schema_sql)
    
    # 1. ข้อมูล Roles และ Users
    cursor.execute("INSERT OR IGNORE INTO roles (role_id, role_name) VALUES (1, 'customer'), (2, 'admin')")
    users = [
        (1, 2, 'admin@ebook.com', 'admin123', 'ผู้ดูแลระบบ'),
        (2, 1, 'somchai@gmail.com', '1234', 'สมชาย ใจดี'),
        (3, 1, 'somsri@gmail.com', '1234', 'สมศรี มณีเนตร'),
        (4, 1, 'ananda@gmail.com', '1234', 'อนันดา สุขสันต์'),
        (5, 1, 'wichai@gmail.com', '1234', 'วิชัย พาณิชย์')
    ]
    cursor.executemany("INSERT OR IGNORE INTO users VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", users)

    # 2. ข้อมูล Categories และ Authors
    categories = [(1, 'การเขียนโปรแกรม'), (2, 'พัฒนาตนเอง'), (3, 'ธุรกิจและการเงิน'), (4, 'นิยายและวรรณกรรม')]
    cursor.executemany("INSERT OR IGNORE INTO categories VALUES (?, ?)", categories)

    authors = [(1, 'สมเกียรติ ช่างคิด'), (2, 'ดร. นิเวศน์'), (3, 'James Clear'), (4, 'ภัทรภณ')]
    cursor.executemany("INSERT OR IGNORE INTO authors VALUES (?, ?)", authors)

    # 3. ข้อมูล E-Books
    ebooks = [
        (1, 1, 1, 'เรียนรู้ Python และ SQL ใน 30 วัน', 'คู่มือพัฒนาเว็บและฐานข้อมูลตั้งแต่พื้นฐาน', 250.00, 1, 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=300'),
        (2, 2, 3, 'Atomic Habits เพราะชีวิตดีได้กว่าที่เป็น', 'วิธีเปลี่ยนนิสัยเล็กๆ สู่ความสำเร็จที่ยั่งยืน', 290.00, 1, 'https://images.unsplash.com/photo-1544716278-ca5e3f4abd8c?w=300'),
        (3, 3, 2, 'เซียนหุ้นมือใหม่', 'หลักการลงทุนแบบเน้นคุณค่าสำหรับมือใหม่', 199.00, 1, 'https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=300'),
        (4, 1, 4, 'สถาปัตยกรรมระบบและฐานข้อมูลสมัยใหม่', 'แนวทางการออกแบบฐานข้อมูลและการทำ Normalize', 350.00, 1, 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=300'),
        (5, 4, 1, 'แดนสนธยา: ปริศนาแห่งรัตติกาล', 'นิยายสืบสวนระทึกขวัญขายดีอันดับหนึ่ง', 180.00, 1, 'https://images.unsplash.com/photo-1512820790803-83ca734da794?w=300')
    ]
    cursor.executemany("INSERT OR IGNORE INTO ebooks VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ebooks)

    # 4. สร้าง Mock Orders ครบ 32 รายการสำหรับใช้ทำรายงานวิเคราะห์
    statuses = ['confirmed', 'confirmed', 'confirmed', 'pending', 'cancelled']
    methods = ['QR PromptPay', 'Bank Transfer', 'Credit Card Mock']
    for i in range(1, 33):
        u_id = random.randint(2, 5)
        status = random.choice(statuses)
        b_id = random.randint(1, 5)
        price = [250.0, 290.0, 199.0, 350.0, 180.0][b_id - 1]
        
        cursor.execute("INSERT OR IGNORE INTO orders (order_id, user_id, total_amount, status, created_at) VALUES (?, ?, ?, ?, datetime('now', ?))",
                       (i, u_id, price, status, f"-{random.randint(1, 28)} days"))
        cursor.execute("INSERT OR IGNORE INTO order_items (order_item_id, order_id, ebook_id, price) VALUES (?, ?, ?, ?)",
                       (i, i, b_id, price))
        
        p_status = 'approved' if status == 'confirmed' else ('pending_verification' if status == 'pending' else 'rejected')
        cursor.execute("INSERT OR IGNORE INTO payments (payment_id, order_id, amount, payment_method, payment_status, proof_url) VALUES (?, ?, ?, ?, ?, ?)",
                       (i, i, price, random.choice(methods), p_status, 'https://placehold.co/400x600?text=Mock+Slip'))
        
        cursor.execute("INSERT OR IGNORE INTO download_links (link_id, order_item_id, download_token, file_url) VALUES (?, ?, ?, ?)",
                       (i, i, f"token-{i}-xyz{random.randint(100,999)}", f"https://mock-storage.local/ebooks/{b_id}.pdf"))

    conn.commit()
    conn.close()
    print("สร้างฐานข้อมูลและข้อมูลจำลอง 32 คำสั่งซื้อเรียบร้อยแล้ว!")

if __name__ == "__main__":
    init()