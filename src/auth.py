# -*- encoding: UTF-8 -*-
#
# Form based authentication for CherryPy. Requires the
# Session tool to be loaded.
#

import cherrypy
import db
import templating
from mysql import connector

import cherrypy
from cherrypy.lib.static import serve_file
from cherrypy.lib.cptools import allow
from cherrypy import HTTPRedirect
from cherrypy import request

import uuid
import hashlib

from mako.template import Template
from mako.lookup import TemplateLookup
import config

lookup = TemplateLookup(directories=['html'])

SESSION_KEY = '_cp_username'
SESSION_USERID = '_cp_userid'

#def hash_password(password):
    # uuid is used to generate a random number
#    salt = uuid.uuid4().hex
#    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt

#def check_password(hashed_password, user_password):
#    password, salt = hashed_password.split(':')
#    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()


#TO HASH PASSWORD hashed_password = hash_password(new_pass)
#check_password(hashed_password, old_pass)


def check_credentials(user, passwd):
    """
    Verifies credentials for username and password.
    Returns None on success or a string describing the error on failure

    >>> type(check_credentials("greg", "gdg"))
    <type 'int'>

    >>> check_credentials("wrong", "used")
    Traceback (most recent call last):
        ...
    LookupError: Incorrect username or password
    """

    cnx = db.connect()[0]
    if cnx:
        cursor = cnx.cursor()
        query = ("SELECT userid from whiley_user where username = %s and password = %s")
        cursor.execute(query, (user, passwd))
        row = cursor.fetchone()
        if cursor.rowcount > 0:
            #print("{} passwd".format(row[2]))
            #hashed_password = hash_password(passwd)
            #if check_password(hashed_password, row[2]):
            result = row[0]
        else:
             raise LookupError("Incorrect username or password")
        cursor.close()
        cnx.close()
    else:
        raise Exception("Unable to connect to database")


    return result

def check_username(user):
    """
    Checks if username exists.
    Returns None on success or a string describing the error on failure

    >>> check_username("usernotcreated")

    >>> check_username("greg")
    'Username not available'
    """

    cnx = db.connect()[0]
    cursor = cnx.cursor()
    query = ("SELECT * from whiley_user where username = %s")
    cursor.execute(query, (user,))
    cursor.fetchall()
    if cursor.rowcount > 0:
        result = "Username not available"
    else:
        result = None
    cursor.close()
    cnx.close()
    return result

def create_username(user, passwd, email, givenname, surname):
    """
    Create username with given information.
    Returns last created ID on success

    >>> type(create_username("newuser", "newpass", "newmail@gmail.com", "newname", "newsurname"))
    <type 'int'>

    # TODO - LASTSID - Change to test with the last id to be created
    """

    #hashed_password = hash_password(passwd)
    cnx = db.connect()[0]
    cursor = cnx.cursor()
    query = "INSERT into whiley_user (username, password, email_address) VALUES (%s, %s, %s)"
    try:
        cursor.execute(query, (user, passwd, email))
    except connector.Error, err:
        print("Error  = %s" % err)
    userid = cursor.lastrowid
    query = "INSERT into student_info (givenname, surname, userid) VALUES (%s, %s, %s)"
    try:
        cursor.execute(query, (givenname, surname, userid))
    except connector.Error, err:
        print("Error  = %s" % err)
    studentid = cursor.lastrowid
    cursor.close()
    cnx.close()
    return userid, studentid


def create_admin(userid):
    """
    Insert userid to admin table
    """
    result = False
    cnx = db.connect()[0]
    cursor = cnx.cursor()
    query = "SELECT * from admin_users where userid = %s"
    cursor.execute(query, (userid,))
    cursor.fetchone()
    if cursor.rowcount > 0:
        result = False
    else:
        query = "INSERT into admin_users (userid) VALUES (%s)"
        cursor.execute(query, (userid,))
        result = True
    cursor.close()
    cnx.close()
    return result

def create_teacher(userid, login, staffid, full_name, preferred_name):
    """
    Inserts userid to the teacher_info table.
    """
    result = False
    cnx = db.connect()[0]
    cursor = cnx.cursor()
    query = "SELECT * from teacher_info where userid = %s"
    cursor.execute(query, (userid,))
    cursor.fetchone()
    if cursor.rowcount > 0:
        result = False
    else:
        query = """INSERT into teacher_info (staffid, login, full_name, preferred_name, userid) 
                    VALUES (%s, %s, %s, %s, %s)"""
        cursor.execute(query, (staffid, login, full_name, preferred_name, userid))
        result = True
    cursor.close()
    cnx.close()
    return result

def insertuserdetails(student_infoid, institutionid, coursesid, validationcode):
    """
    Create username with given information.
    Returns error= False if user is updated | error = True if course id or validationcode is wrong
    """
    cnx = db.connect()[0]
    cursor = cnx.cursor()
    #check if validation is correct
    query = "SELECT * FROM course WHERE courseid = %s and validationcode = %s"
    cursor.execute(query, (coursesid, validationcode))
    row = cursor.fetchone()
    if cursor.rowcount > 0:
        #validation is correct so update institution to user
        query = "UPDATE student_info SET institutionid=%s WHERE student_info_id=%s"
        cursor.execute(query, (institutionid, student_infoid))
        #create link between user and course
        query = "INSERT INTO student_course_link VALUES (%s, %s)"
        cursor.execute(query, (student_infoid, coursesid))
        error = False
    else:
        error = True
    cursor.close()
    cnx.close()
    return error


def check_auth(*args, **kwargs):
    """A tool that looks in config for 'auth.require'. If found and it
    is not None, a login is required and the entry is evaluated as a list of
    conditions that the user must fulfill"""
    conditions = cherrypy.request.config.get('auth.require', None)
    if conditions is not None:
        username = cherrypy.session.get(SESSION_KEY)
        userid = cherrypy.session.get(SESSION_USERID)
        if userid:
            cherrypy.request.login = username
            for condition in conditions:
                # A condition is just a callable that returns true or false
                if not condition():
                    raise cherrypy.HTTPRedirect("/auth/login")
        else:
            raise cherrypy.HTTPRedirect("/auth/login")

cherrypy.tools.auth = cherrypy.Tool('before_handler', check_auth)



def require(*conditions):
    """A decorator that appends conditions to the auth.require config
    variable."""
    def decorate(f):
        if not hasattr(f, '_cp_config'):
            f._cp_config = dict()
        if 'auth.require' not in f._cp_config:
            f._cp_config['auth.require'] = []
        f._cp_config['auth.require'].extend(conditions)
        return f
    return decorate


# Conditions are callables that return True
# if the user fulfills the conditions they define, False otherwise
#
# They can access the current username as cherrypy.request.login
#
# Define those at will however suits the application.

def member_of(groupname):
    def check():
        # replace with actual check if <username> is in <groupname>
        return cherrypy.request.login == 'joe' and groupname == 'admin'
    return check

def name_is(reqd_username):
    return lambda: reqd_username == cherrypy.request.login

def requireAdmin(userid):
    """
    Require admin role to show the page, raise an error if user is not admin
    """
    if not isAdmin(userid):
        raise cherrypy.HTTPRedirect("/auth/login")

def requireAdminOrTeacher(userid):
    """
    Require either an admin or teacher role to show the page, rasie an error if user is not
    """
    if not isAdmin(userid) and not isTeacher(userid):
        raise cherrypy.HTTPRedirect("/auth/login")

def isTeacher(userid):
    """
    Checks if username is a teacher. 
    Returns True on success or False on failure
    """
    result = False
    cnx = db.connect()[0]
    if cnx:
        cursor = cnx.cursor()
        query = ("SELECT teacherid FROM teacher_info WHERE userid = %s")
        cursor.execute(query, (userid,))
        row = cursor.fetchone()
        if cursor.rowcount > 0:
            result = True
        cursor.close()
        cnx.close()
    else:
        print "Unable to connect to database"
    print userid, "is teacher:", result
    return result
        
def isAdmin(userid):
    """
    Checks if username is admin.
    Returns True on success or False on failure

    >>> isAdmin(01)
    True
    >>> isAdmin(02)
    False
    """
    result = False
    cnx = db.connect()[0]
    if cnx:
        cursor = cnx.cursor()
        query = ("SELECT adminid from admin_users where userid = %s")
        cursor.execute(query, (userid,))      
        row = cursor.fetchone()
        if cursor.rowcount > 0:
            result = True
        cursor.close()
        cnx.close()
    else:
        print "Unable to connect ot database"
    return result
# Controller to provide login and logout actions

class AuthController(object):

    @cherrypy.expose
    def login(self, user=None, passwd="", from_page="/"):
        """Login the user
        Success: Create session and redirect to 'from_page'
        Wrong user: Render login page with error message
        User = None: Show login page


        """
        if user is None:
            #return self.get_loginform("", from_page=from_page)
            template = lookup.get_template("login.html")
            error = False
            return template.render(ERROR=error)
            #raise cherrypy.HTTPRedirect("/")
        try:
            userid = check_credentials(user, passwd)
        except Exception as excep:
            error = True
            template = lookup.get_template("login.html")
            return template.render(ERRORMSG=excep.message, USERNAME=user, ERROR=excep.message)
        cherrypy.session.regenerate()
        cherrypy.session[SESSION_KEY] = cherrypy.request.login = user
        cherrypy.session[SESSION_USERID] = cherrypy.request.userid = userid
        #return cherrypy.session[SESSION_KEY]
        raise cherrypy.HTTPRedirect(from_page)

    @cherrypy.expose
    def signup(self, user="", passwd="", email="", cpasswd="", givenname="", surname="", enrolled=False):
        """Sign the user up
        Success: Create session and redirect to root
        Errors: Empty fields, passwords do no match, username already exists

        """
        #create_username("test", "ẗest", "testemail")
        print user
        if user == "" or passwd == "" or email == "" or givenname == "" or surname == "":
            error_msg="All fields are required"
            template = lookup.get_template("signup.html")
            error = True
            return template.render(ERROR=error, ERRORMSG=error_msg)
        elif passwd != cpasswd:
            error_msg="Passwords do not match"
            template = lookup.get_template("signup.html")
            error = True
            return template.render(ERROR=error, ERRORMSG=error_msg)
        error_msg = check_username(user)
        if error_msg is None:
            userid, studentid = create_username(user, passwd, email, givenname, surname)
            cherrypy.session.regenerate()
            cherrypy.session[SESSION_KEY] = cherrypy.request.login = user
            cherrypy.session[SESSION_USERID] = cherrypy.request.userid = userid
            if enrolled is not False:
                #send user to institutions page
                return self.user_courses(studentinfoid=studentid)
            else:
                message="User Created, Welcome! Redirecting..."
                template = lookup.get_template("redirect.html")
                return template.render(STATUS="alert-success", MESSAGE=message)
        else:
            error_msg="Username already exists, choose another one"
            template = lookup.get_template("signup.html")
            error = True
            return template.render(ERROR=error, ERRORMSG=error_msg)

    @cherrypy.expose
    def user_courses(self, studentinfoid=None, institution="", validationcode="", courseid="", *args, **kwargs):
        """Assign user to select course
        
        """
        if studentinfoid is None:
            raise cherrypy.HTTPRedirect("/")
        allow(["HEAD", "GET", "POST"])
        error = False
        error_msg = " "
        redirect = "NO"
        options = []

        course_list = []
        
        if institution:
            cnx, status = db.connect()
            cursor = cnx.cursor() 
            query = ("SELECT institutionid,institution_name from institution order by institution_name")
            cursor.execute(query) 
            options = list(cursor)
            cursor.close()

        if courseid:
            cnx, status = db.connect()
            cursor = cnx.cursor() 
            error = insertuserdetails(studentinfoid, institution, courseid, validationcode)
            cursor.close()
            if error is False:
                message="User Created, Welcome! Redirecting..."
                template = lookup.get_template("redirect.html")
                return template.render(STATUS="alert-success", MESSAGE=message)
            else:
                error_msg= "Wrong Validation Code"

        if institution == "":          
            cnx, status = db.connect()
            cursor = cnx.cursor() 
            query = ("SELECT institutionid,institution_name from institution order by institution_name")
            cursor.execute(query)
            for (institutionid,institution_name) in cursor:
                options.append((institutionid, institution_name))
                if institution == "":
                    institution = str(institutionid)
            cursor.close()

        ##get courses list
        cnx, status = db.connect()
        cursor = cnx.cursor() 
        query = ("SELECT courseid,code from course where institutionid = '" + institution + "' order by code")
        cursor.execute(query)
        course_list = list(cursor)
        cursor.close()

        return templating.render("user_institutions.html", ERROR=error, ERRORMSG=error_msg, NOTALLOWED=False, 
                                ROOT_URL=config.VIRTUAL_URL, OPTION=options, 
                                COURSE_LIST=course_list, STUDENTINFOID=studentinfoid, INSTITUTION=institution)


    @cherrypy.expose
    def logout(self, from_page="/"):
        sess = cherrypy.session
        username = sess.get(SESSION_KEY, None)
        userid = sess.get(SESSION_USERID, None)
        sess[SESSION_KEY] = None
        sess[SESSION_USERID] = None
        if username:
            cherrypy.request.login = None
        if userid:
            cherrypy.request.userid = None
            #self.on_logout(username)
        raise cherrypy.HTTPRedirect("/")
