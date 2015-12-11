#!/bin/python
import swiftclient
from swiftclient import ClientException
from six.moves import configparser
import os,sys,commands
import datetime
import time
import logging
from logging.handlers import TimedRotatingFileHandler
from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib
import pdb

logger = None
# Setup global logger
logger_dir=os.getcwd() + "/log/"
if not os.path.exists(logger_dir):
    os.makedirs(logger_dir)

class Config(object):
    def __init__(self, conf_file=None):
        if conf_file:
            self.config_file = conf_file
            self._get_config(specified=True)
        else:
            self._get_config()

    def _get_config(self, specified=False):
        if specified is True:
            config_file = self.config_file
        else:
            config_file = os.environ.get('SWIFTCLIENT_CONFIG_FILE',
                                     './backup.conf')
        config = configparser.SafeConfigParser({'auth_version': '1'})
	config.read(config_file)
        if config.has_section('swiftconf'):
            auth_host = config.get('swiftconf', 'auth_host')
            auth_port = config.getint('swiftconf', 'auth_port')
            auth_ssl = config.getboolean('swiftconf', 'auth_ssl')
            auth_prefix = config.get('swiftconf', 'auth_prefix')
            self.auth_version = config.get('swiftconf', 'auth_version')
            self.account = config.get('swiftconf', 'account')
            self.username = config.get('swiftconf', 'username')
            self.password = config.get('swiftconf', 'password')
            self.container_mysql = config.get('swiftconf', 'container_name')
            self.auth_url = ""
            if auth_ssl:
                self.auth_url += "https://"
            else:
                self.auth_url += "http://"
            self.auth_url += "%s:%s%s" % (auth_host, auth_port, auth_prefix)
            if self.auth_version == "1":
                self.auth_url += 'v1.0'
            self.account_username = "%s:%s" % (self.account, self.username)
        if config.has_section('agentconf'):
            self.db_username = config.get('agentconf','DB_USERNAME')
            self.db_passwd = config.get('agentconf','DB_PASSWD')
            self.db_name = config.get('agentconf','DB_NAME')
            self.db_expire_days = config.get('agentconf','DB_EXPIRE_DAYS')
            self.db_backup_dir = config.get('agentconf','BACK_DIR')
            self.admin_email = config.get('agentconf','ADMIN_EMAIL')

def create_timed_rotating_log(logfile):
    """"""
    global logger
    logger = logging.getLogger("Rotating Log")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    handler = TimedRotatingFileHandler(logfile,
                                       when="midnight",
                                       interval=1,
                                       backupCount=30)
    handler.setFormatter(fmt)
    if not logger.handlers:
        logger.addHandler(handler)

def backup_mysql(db_username,db_passwd,db_name,db_backup_dir,db_backup_name):
    (status,output) = commands.getstatusoutput("mysqldump -u%s -p%s %s > %s/%s " % (db_username,db_passwd,db_name,db_backup_dir,db_backup_name))
    logger.debug(output)
    if status == 0:
        logger.info("Backup db: %s successful!" % db_backup_name)
        return True
    else:
        logger.error("BAckup db: %s error!" % db_backup_name)
        return False

def caculate_expire_date(current_time, deltadays):
    expire_time = current_time - datetime.timedelta(days=int(deltadays))
    expire_date = expire_time.strftime("%Y-%m-%d")
    logger.debug("expire date is %s " % expire_date)
    return expire_date 
    

def remove_expire_object(swiftclient,container_name,object_name):
    logger.info("Starting to remove the expire object : %s on cloud" % object_name)
    try:
        swiftclient.delete_object(container_name,object_name)
        return True
    except:
        logger.error("No object: %s found in container %s" % (object_name,container_name))
        return False


def upload_object(conn,container_name,object_name):
    logger.info("Starting to upload the object: %s" % object_name)
    db_content = open(object_name)
    try:
        conn.put_object(container_name,object_name,contents=db_content)
        return True
    except:
        logger.error("Upload object %s to container %s failed!" %(object_name.container_name))
        return False


def send_mail(mail_type,admin_email,object_name):
  #  def _format_addr(s):
  #      name, addr = parseaddr(s)
  #      return formataddr(( \
  #          Header(name, 'utf-8').encode(), \
  #          addr.encode('utf-8') if isinstance(addr, unicode) else addr))
    logger.info("Will send mail to admin!")
    from_addr = "backup_server@rc.inesa.com"
    to_addr = admin_email
    smtp_server = "localhost"
    if mail_type=="successful":
        msg = MIMEText('Database %s backup successful!' % object_name,'plain', 'utf-8' )
        msg['Subject'] = Header(u'backup for %s successful!' % object_name, 'utf-8').encode()

    if mail_type == "error":
        msg = MIMEText('database %s backup failed!' % object_name ,'plain', 'utf-8' )
        msg['Subject'] = Header(u'backup for %s failed!' % object_name, 'utf-8').encode()


    msg['From'] =  from_addr
    msg['To'] =  to_addr

    server = smtplib.SMTP(smtp_server)
    server.set_debuglevel(1)
    server.sendmail(from_addr, [to_addr], msg.as_string())
    logger.info("send mail finished")
    server.quit()

def main():
    conf = Config()
    logfile= logger_dir + "backup.log"
    create_timed_rotating_log(logfile)
    current_time = datetime.datetime.now()
    backup_date = datetime.datetime.now().strftime("%Y-%m-%d")
    expire_date = caculate_expire_date(current_time,conf.db_expire_days)

    #create connection to swift
    conn = swiftclient.Connection(conf.auth_url,
                                  conf.account_username,
                                  conf.password,
                                  auth_version=conf.auth_version)
    logger.info("The swifclient object is %s" % conn)
    #pdb.set_trace()

    # check if container exists, create one if not
    try:
        head_container = conn.head_container(conf.container_mysql)
        logger.debug('head container: %s' % json.dumps(head_container,
            sort_keys=True, indent=4))
    except:
        logger.info('container not exists or swift connection fail...')
        conn.put_container(conf.container_mysql)
        logger.info('created container...')
    #backup database
    db_backup_name = conf.db_name + "-" + backup_date
    pdb.set_trace()
    full_db_backup_name = conf.db_backup_dir + "/" + db_backup_name
    compress_db_name = full_db_backup_name +".tar.gz"
    logger.debug("The db_backup_name is %s " % compress_db_name)
    backup_result = backup_mysql(conf.db_username,conf.db_passwd,conf.db_name,conf.db_backup_dir,db_backup_name)
    logger.info("Compress backup db to %s !" % compress_db_name)
    (status,output) = commands.getstatusoutput("tar czf %s %s" % (compress_db_name,full_db_backup_name))
    if status == 0:
        logger.info("Delete local backup db %s due to already compress it!" % full_db_backup_name)
        (status,output) = commands.getstatusoutput("rm -f %s" % full_db_backup_name)
    compress_expire_db_name = conf.db_name + "-" + expire_date + ".tar.gz"
    full_compress_expire_db_name = conf.db_backup_dir + compress_expire_db_name
    logger.debug("The full_compress_expire_db_name is %s " % compress_expire_db_name)
    if backup_result == True:
        logger.info("Remove local compress expire db %s " % full_compress_expire_db_name)
        (status,output) = commands.getstatusoutput("rm -f  %s " % full_compress_expire_db_name)
        remove_expire_object(conn,conf.container_mysql,compress_expire_db_name)
        upload_result = upload_object(conn,conf.container_mysql,compress_db_name)
        send_mail("successful",conf.admin_email,db_backup_name)
    else:
        send_mail("error",conf.admin_email,db_backup_name)
    
if __name__ == "__main__":
   main()
