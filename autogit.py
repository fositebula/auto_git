# coding=utf-8
import time

import sh
from sh import ErrorReturnCode
import sys

from git import Repo
from git.exc import GitCommandError
import requests
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from requests import ConnectionError
from smtpd import COMMASPACE
import smtplib
from config import GIT_REPOSITORY_PATH

import logging
import logging.handlers

logger = logging.getLogger(__name__)

#for gerrit
USER = 'dongpl'
PASSWD = 'dongpl123'

#for mail
TO_SOMEONE = ["dongpl@spreadst.com"]
MAIL_ACCOUNT = "pl.dong@spreadtrum.com"
PASSWD = "123@afAF"
MAIL_FROM = "Auto Git <pl.dong@unisoc.com>"
SMPT_HOST = "smtp.unisoc.com"
SMPT_PORT = 587
DOCMD = "ehlo"

#for logger
LOG_FILE = "./autogit.log"
LOG_LEVEL = logging.INFO

#return code
FAIL = 'Fail'
SUCCESS = 'Success'
NO_CHANGE = 'No Change'
GERRIT_ERROR = 'Gerrit Error'
COPY_ERROR = 'Copy Error'

class AutoGitException(Exception):
    pass

def logger_init():
    logger.setLevel(level = LOG_LEVEL)
    handler = logging.FileHandler(LOG_FILE)
    handler.setLevel(LOG_LEVEL)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def send_mail(sub, content, send_mail_list):
    try:
        mail_obj = smtplib.SMTP(SMPT_HOST, SMPT_PORT)
        mail_obj.docmd(DOCMD, MAIL_ACCOUNT)
        mail_obj.starttls()
        mail_obj.login(MAIL_ACCOUNT, PASSWD)
        msg = MIMEMultipart()
        msg['From'] = MAIL_FROM
        msg['To'] = COMMASPACE.join(send_mail_list)
        msg['Subject'] = sub
        con = MIMEText(content, 'html', 'utf-8')
        msg.attach(con)
        mail_obj.sendmail(MAIL_ACCOUNT, send_mail_list, msg.as_string())
        mail_obj.quit()
    except:
        # traceback.print_exc()
        logger.error(traceback.format_exc())

def sh_git(message):
    import subprocess
    import re
    sh.cd(GIT_REPOSITORY_PATH)
    repo = Repo(GIT_REPOSITORY_PATH)
    old_commitid = repo.heads[0].commit.hexsha
    sh.git(['add', 'joint_complie.json'])
    sh.git(['commit', '-m', message])
    #git push ssh://dongpl@review.source.spreadtrum.com:29418/scm/etc/build HEAD:refs/for/master
    ret = subprocess.Popen(['git', 'push', '--no-thin', 'ssh://dongpl@review.source.spreadtrum.com:29418/scm/etc/build', 'HEAD:refs/for/master']
                    , stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ret.wait()
    stdr = ret.stderr.read()
    gerrit_id = re.findall('http.*gerrit\/(\d+)', stdr, re.S)
    if len(gerrit_id) == 0:
        #如果无法push就回退
        sh.git(['reset', '--hard', old_commitid])
        raise AutoGitException('Push Error: {}'.format(stdr))
    return gerrit_id[0]

def main(message):
    repo = Repo(GIT_REPOSITORY_PATH)
    if not repo.is_dirty():
        print NO_CHANGE
        return
    try:
        gerritid = sh_git(message)
    except GitCommandError:
        # traceback.print_exc()
        send_mail('Auto Git Main GitCommandError', traceback.format_exc(), TO_SOMEONE)
        print FAIL
        return
    except Exception as e:
        # traceback.print_exc()
        send_mail('Auto Git Main GitCommandError', traceback.format_exc(), TO_SOMEONE)
        print FAIL
        return

    commit_id = repo.heads[0].commit.hexsha
    ret = gerrit_verify_review_submit(commit_id, gerritid)
    print ret

def gerrit_verify_review_submit(commitid, gerrit_id):
    try:
        s = requests.Session()
        res = s.get("http://review.source.spreadtrum.com/gerrit/login/", auth=('dongpl', 'dongpl123'))
        # print 'Gerrit ID :', gerrit_id
        # print 'Commit ID :', commitid
        #获取X-Gerrit-Auth
        res = s.get("http://review.source.spreadtrum.com/gerrit/changes/?q=change:{}+has:draft&O=0".format(gerrit_id))
        headers = res.request.headers
        X_Gerrit_Auth = headers['Cookie'].split('=')[-1]
        headers['X-Gerrit-Auth'] = X_Gerrit_Auth

        #执行打分并合入
        verify_review_url = 'http://review.source.spreadtrum.com/gerrit/changes/{}/revisions/{}/review'.format(gerrit_id, commitid)
        submit_url = 'http://review.source.spreadtrum.com/gerrit/changes/{}/revisions/{}/submit'.format(gerrit_id, commitid)
        post_data = {"labels":{"Code-Review":2,"Verified":1},"strict_labels":True,"drafts":"PUBLISH_ALL_REVISIONS"}
        res = s.post(verify_review_url, headers=headers, json=post_data)
        # print res.status_code
        res = s.post(submit_url, headers=headers, json=post_data)
        if res.status_code == 409:
            send_mail('Auto Git exception', 'Gerrit Error: gerrit id: {}'.format(gerrit_id), TO_SOMEONE)
            return GERRIT_ERROR
        # print res.status_code
        if res.status_code == 200:
            return SUCCESS
    except ConnectionError:
        send_mail('Auto Git ConnectionError', "ConnectionError", TO_SOMEONE)
        time.sleep(18)
        gerrit_verify_review_submit(commitid)
    except:
        send_mail('Auto Git exception', traceback.format_exc(), TO_SOMEONE)
        return FAIL


if __name__ == '__main__':
    try:
        source_path = sys.argv[1]
        sh.cp(source_path, GIT_REPOSITORY_PATH)
    except ErrorReturnCode:
        send_mail('Auto Git exception', traceback.format_exc(), TO_SOMEONE)
        exit(COPY_ERROR)

    main('test')