import sqlite3

DB= sqlite3.connect('University.db')

cursor=DB.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS student(std_ID int, std_name text, std_age int)")

cursor.execute("CREATE TABLE IF NOT EXISTS registered_courses(std_ID int, course_ID int)")

cursor.execute("CREATE TABLE IF NOT EXISTS grades(std_ID int, course_ID int, grade int)")

cursor.execute("INSERT INTO student values(1,'Mohamad',20)")
cursor.execute("INSERT INTO student values(2,'Maya',21)")


cursor.execute('INSERT INTO grades values(1,100,90)')
cursor.execute('INSERT INTO grades values(1,101,80)')
cursor.execute('INSERT INTO grades values(2,101,85)')

DB.commit()

cursor.execute("SELECT std_ID, MAX(grade) FROM grades GROUP by std_ID")
print('MAX grade=',cursor.fetchall())

cursor.execute("SELECT std_ID, AVG(grade) FROM grades GROUP by std_ID")
print('AVG grade=',cursor.fetchall())

DB.close()

