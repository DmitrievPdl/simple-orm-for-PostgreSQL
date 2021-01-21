# Simple ORM for PostgreSQL

ORM (Object-Relational Mapping) – технология программирования, которая связывает базы данных с концепциями объектно-ориентированных языков программирования, создавая «виртуальную объектную базу данных».

Реализована простая версия ORM для базы данных PostgreSQL, которая имеет такой же синтаксис как у Django. Пример использования:

```python
class Goods(models.Model):
    name = models.CharField(max_lenght = 50)
    price = models.IntegerField()
    description = models.TextField()
    def __init__(self, name, price, description):
        self.name = name
        self.price = price
        self.description = description

apple = Goods('apple', 35, 'delicious sweet apple')
book = Goods('book', 140, 'fantasy')
apple.save()
book.save()
book.name = "The Hitchhikers Guide to the Galaxy"
book.update()
```

В итоге в базе данных мы будем иметь такую таблицу ```Goods```:

```sql
 id |                name                 | price |      description
----+-------------------------------------+-------+-----------------------
  1 | apple                               |    35 | delicious sweet apple
  2 | The Hitchhikers Guide to the Galaxy |   140 | fantasy
(2 rows)
```

Также возможен вывод данных в таблице через ```manager``` - метод класса ```Model```, который отвечает за взаимодействие класса с базой данных.

```python
manager = Goods.manager()
manager.all()
```

Получим:

```python
(1, 'apple', 35, 'delicious sweet apple')
(2, 'The Hitchhikers Guide to the Galaxy', 140, 'fantasy')
```

## class Database

```python
class Database:
    ''' Class to access psycopg2.connect method '''

    def __init__(self):

        ''' Create SQL connection '''
        self.connection = psycopg2.connect(
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        self.connected = True

    def close(self):
        ''' Close SQL connection '''
        if self.connected:
            self.connection.close()
        self.connected = False

    def commit(self):
        ''' Commit SQL changes '''
        self.connection.commit()

    def execute(self, sql):
        ''' Execute SQL '''
        cursor = self.connection.cursor()
        cursor.execute(sql)
        cursor.close()

    def executescript(self, script):
        ''' Execute SQL script '''
        cursor = self.connection.cursor()
        cursor.execute(script)
        try:
            records = cursor.fetchall()
            cursor.close()
            self.commit()
            return records
        except psycopg2.ProgrammingError:
            cursor.close()
            self.commit()
```

В конструкторе класса мы подключаемся к базе данных. Также определены несколько методов для взаимодействия с базой данных.
Метод ```executescript``` записывает переданный код ```script``` в базу данных. Если есть какой-то ответ от базы данных (например, когда ```script``` содержит ```SELECT```), то полученные данные возвращаются. В противном случае, метод ничего не возвращает.

## class Manager

```python
class Manager(object):
    ''' Data mapper interface (generic repository) for models '''

    def __init__(self, db, model):
        self.db = db
        self.model = model
        self.table_name = model.__name__
        # create table if not exist
        self.db.executescript(render_create_table(self.model))

    def save(self, obj):
        ''' Save a model object '''
        name_col = []
        value_col = []
        attrs_dict = attrs(obj)
        for key in attrs_dict.keys():
            name_col += [key]
            if isinstance(attrs_dict[key], int):
                value_col += [str(attrs_dict[key])]
            else:
                value_col += ["'" + str(attrs_dict[key]) +"'"]
        column_names = "%s" % ", ".join(name_col)
        column_values = "%s" % ", ".join(value_col)

        sql = 'INSERT INTO %s (%s) VALUES (%s)  RETURNING id;'
        sql = sql % (self.table_name, column_names, column_values)

        ''' write the object to the database and add the id attribute
            id - primary key in database'''
        obj.id = self.db.executescript(sql)[0][0]

    def delete(self, obj):
        ''' Delete a model object from database '''
        sql = 'DELETE FROM %s WHERE id = %d;'
        self.db.executescript(sql % (self.table_name, obj.id))

    def update(self, obj):
        self.delete(obj)
        self.save(obj)

    def all(self):
        sql = 'SELECT * FROM %s' % self.table_name
        rows = self.db.executescript(sql)
        for row in rows:
            print(row)
```

Класс является переходным мостиком между базой данных и классом, созданным пользователем. При создании экземпляра класса ```Manager``` он получает доступ к базе данных и к модели. Стоит отметить, что в конструкторе создается таблица для нужной модели, если она еще не была создана. Таблица создается с встроенным primary key, вне зависимости от определения полей в классе унаследованном от ```Model``` с помощью ``` id BIGSERIAL NOT NULL PRIMARY KEY ```. Более подробно о том какой код sql выполняется при создании таблицы можно посмотреть в функции ```render_create_table```.

Перейдем к методам класса ```Model```.

Метод ```save``` принимает экземпляр класса и сохраняет его в базу данных. Также добавляет новое поле для него - id, который как уже упоминалось является первичным ключем.

Метод ``` delete ``` принимает удаляет переданный ему экземпляр класса. Метод ```update``` нужен если мы произвели некоторые изменения в экземпляре класса и хоти сохранить данные изменеия в базу данных. Он удаляет старую строку соответствующую экземпляру класса и сохраняет уже изменный.

Метод ```all``` выводит все строки таблицы в командную строку.

## class Model

```python
class Model(object):
    ''' Abstract entity model with an active record interface '''

    db = Database()

    def delete(self):
        ''' Delete this model object '''
        return self.__class__.manager().delete(self)

    def save(self):
        ''' Save this model object '''
        return self.__class__.manager().save(self)

    def update(self):
        ''' Update this model object '''
        return self.__class__.manager().update(self)

    @classmethod
    def manager(cls):
        ''' Create a database managet '''
        return Manager(cls.db, cls)
```

Класс ```Model``` имеет метод класса ```manager```, который по сути является одним и тем же для всех экземпляров класса,унаследованного от ```Model```. Все его методы инкапсулируют основные методы класса ```manager```, чтобы сделать удобный интерфейс для пользователя.

Стоит также упомянуть о реализации полей для моделей. Их всего 3 :

1. ```CharField(max_lenght = ...)``` - текст ограниченной длины

2. ```TextField()``` - текст неограниченной длины

3. ```IntegreField()``` - число типа ```int```

Они реализованы в модуле ```fields.py``` с помощью дескрипторов, причем методы ```__set__``` содержат валидацию, характерную для каждого типа полей.
