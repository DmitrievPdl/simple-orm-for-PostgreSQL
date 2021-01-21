import psycopg2
from fields import CharField, IntegerField, TextField
import orm_logger

logger = orm_logger.get_logger(__name__)
DB_NAME = 'database_test_orm'
DB_USER = 'postgres'
DB_PASSWORD = 'PASSWORD'
DB_HOST = '127.0.0.1'
DB_PORT = '5432'

def attrs(obj):
    ''' Return public attribute values dictionary for an object '''
    return dict(i for i in vars(obj).items() if i[0][0] != '_')

def copy_attrs(obj, remove=None):
    ''' Copy attribute values for an object '''
    if remove is None:
        remove = []
    return dict(i for i in attrs(obj).items() if i[0] not in remove)

def render_column_definitions(model):
    ''' Create postgresql column definitions for an entity model '''
    model_attrs = attrs(model).items()
    model_attrs = {k: v for k, v in model_attrs if k != 'db'}
    return ['%s %s' % (k, v) for k, v in model_attrs.items()]

def render_column_values_str(obj):
    ''' Create two string the first contains a field name, the second values of field '''
    attrs_dict = attrs(obj)
    colms = ''
    values = ''
    for k in attrs_dict.keys():
        colms += ', %s' % k
        if isinstance(attrs_dict[k], int) or isinstance(attrs_dict[k], float):
            values += ', %s' % attrs_dict[k]
        else:
            values += ", '%s'" % attrs_dict[k]
    return (colms[1:], values[1:])

def render_create_table(model):
    ''' Render a postgresql statement to create a table for an entity model '''
    sql = 'CREATE TABLE IF NOT EXISTS {table_name} (id BIGSERIAL NOT NULL PRIMARY KEY, {column_def});'  # noqa
    column_definitions = ', '.join(render_column_definitions(model))
    params = {'table_name': model.__name__, 'column_def': column_definitions}
    return sql.format(**params)

class Database:
    ''' Class to access psycopg2.connect method '''

    def __init__(self):

        ''' Create SQL connection '''
        try:
            self.connection = psycopg2.connect(
                database=DB_NAME, 
                user=DB_USER,
                password=DB_PASSWORD, 
                host=DB_HOST, 
                port=DB_PORT
            )
            self.connected = True
        except psycopg2.OperationalError:
            logger.warning("Failed to connect to database")
            self.connected = False
            raise psycopg2.OperationalError("Failed to connect to database")

    def close(self):
        ''' Close SQL connection '''
        if self.connected:
            self.connection.close()
        self.connected = False

    def commit(self):
        ''' Commit SQL changes '''
        self.connection.commit()
    
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

class Manager(object):
    
    ''' Data mapper interface (generic repository) for models '''
    def __init__(self, db, model):
        self.db = db
        self.model = model
        self.table_name = model.__name__
        
        ''' Create table if not exist '''
        self.db.executescript(render_create_table(self.model))

    def save(self, obj):
        ''' Save a model object '''
        logger.info(f'Try to save {self.table_name} object with id = {obj.id}.')

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

        ''' Write the object to the database and add the id attribute
            id - primary key in database'''

        obj.id = self.db.executescript(sql)[0][0]
        if obj.id:
            logger.info(f'The {self.table_name} object with id = {obj.id} successfully saved in database')
        else:
            logger.error(f'The {self.table_name} object ({obj}) is not entered into the database')

    def delete(self, obj):
        ''' Delete a model object from database '''
        logger.info(f"Try to remove {self.table_name} object with id = {obj.id} from database.")
        try:
            id  = obj.id
        except AttributeError:
            logger.error(f'The {self.table_name} object with id = {obj.id} cannot be removed from database')
            raise AttributeError("This object has not yet been entered into the database")
        
        ''' Return error if object with id doesn't exist in database'''
        deleted_obj = self.get(id)
        sql = 'DELETE FROM %s WHERE id = %d;'
        self.db.executescript(sql % (self.table_name, id))
        
        logger.info(f"The {self.table_name} object with id = {obj.id} successfully  removed from database.")
        return deleted_obj

    def update(self, obj):
        ''' Update exist model object  '''
        logger.info(f"Try to update {self.table_name} object with id = {obj.id}.")
        
        try:
            id = obj.id
        except AttributeError:
            logger.error(f"The {self.table_name} object with id = {obj.id} cannot be update")
            raise AttributeError("This object has not yet been entered into the database.")

        sql = ' UPDATE %s SET (%s) = (%s) WHERE id = %s;'
        (colms, new_values) = render_column_values_str(obj)
        self.db.executescript(sql % (self.table_name, colms, new_values, id))
        
        logger.info(f"The {self.table_name} object with id = {obj.id} successfully update.")

    def all(self):
        ''' Get all model objects from database '''
        arg_values = self.db.executescript('SELECT * FROM %s' % self.table_name)
        output = []

        if not arg_values:
            msg = 'Database is empty'
            logger.error(msg)
            raise ValueError(msg)

        for args in arg_values:
            output += [self.create(args)]
        return output
    
    def get(self, id):
        ''' Get a model object from database by its id '''
        logger.info(f'Try to get {self.table_name} odject with id = {id}.')
        sql = 'SELECT * FROM %s WHERE id = %s' % (self.table_name, id)
        arg_values = self.db.executescript(sql)

        if not arg_values:
            msg = 'Object with id = %s does not exist in database' % (id)
            logger.error(f'Faild to get {self.table_name} odject with id = {id}.')
            raise ValueError(msg)
        
        logger.info(f'{self.table_name} odject with id = {id} successfully get.')
        return self.create(arg_values[0])

    def create(self, arg_values):
        ''' Create a single model object '''
        obj = object.__new__(self.model)
        fields = attrs(self.model).keys()
        id = arg_values[0]
        kwargs = dict(zip(fields, arg_values[1:]))
        obj.__dict__ = kwargs
        obj.id = id
        return obj

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

    @property
    def public(self):
        ''' Return the public model attributes '''
        return attrs(self)

    def __repr__(self):
        return str(self.public)

    def __str__(self):
        return f"{self.__class__.__name__} object: {self.public}>"
