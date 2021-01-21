

class Field():

    def __get__(self, instance, owner):
        return instance.__dict__[self.name]

    def __set_name__(self, owner, name):
        self.name = name
    
    @staticmethod
    def valid_short_str(value, max_lenght):
        if isinstance(value, str) and len(value) <= max_lenght:
            return value
        else:
            raise ValueError('''Wrong format. The field must contain a string type variable
                            and must be no longer than %d'''% max_lenght)

    @staticmethod
    def valid_long_str(value):
        if isinstance(value, str):
            return value
        else:
            raise ValueError('''Wrong format. the field must contain a string type variable ''')

    @staticmethod
    def valid_int(value):
        if isinstance(value, int):
            return value
        else:
            raise ValueError('''Wrong format. the field must contain a int type variable ''')


class CharField(Field):

    def __init__(self, max_lenght):
        self.max_lenght = max_lenght

    def __set__(self, instance, text):
        instance.__dict__[self.name] = Field.valid_short_str(text, self.max_lenght)

    def __repr__(self):
        return 'VARCHAR(%d)' % self.max_lenght

class TextField(Field):

    def __set__(self, instance, text):
        instance.__dict__[self.name] = Field.valid_long_str(text)

    def __repr__(self):
        return 'TEXT'

class IntegerField(Field):

    def __set__(self, instance, number):
        instance.__dict__[self.name] = Field.valid_int(number)
    
    def __repr__(self):
        return 'INT'