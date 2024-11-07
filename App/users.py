class Users:
    def __init__(self,username,password,privillege):
        self.__username=username
        self.__password=password
        self.__privillege=privillege
    def get_userinfo(self,usernaem,password,privillege):
        return self.__username,self.__password,self.__privillege
    def set_userinfo(self):
        self.__username,self.__password,self.__privillege