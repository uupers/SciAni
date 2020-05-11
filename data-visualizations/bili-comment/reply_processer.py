import datetime
import eventlet
eventlet.monkey_patch(thread=False)
import json
import os
import pickle
import random
import re
import requests
import shutil
# import socket
import sys
import threading
import time



""" Global variables """
mid = 546195 # 老番茄


""" Assitant functions """

def headers():
    return { "user-agent": "botnet - {}".format(random.random()) }

def join_path(*args):
    return os.path.join(*args).replace("\\","/")

def dt2ct(dt):
    return datetime.datetime.timestamp(dt)

def ct2dt(ct):
    return datetime.datetime.fromtimestamp(ct)

def dt2str(dt):
    return dt.strftime("%Y-%m-%d-%H-%M-%S")

def dt2dt0(dt,hour=0):
    return datetime.datetime(dt.year,dt.month,dt.day,hour,0,0)

def ct2dt0(ct):
    return dt2dt0(ct2dt(ct))

V_TABLE="fZodR9XQDSUm21yCkr6zBqiveYah8bt4xsWpHnJE7jL5VG3guMTKNPAwcF"
V_MAP={}
for i in range(58):
    V_MAP[V_TABLE[i]]=i
V_OFFSET=[11,10,3,8,4,6]
V_ADD, V_XOR = 8728348608, 177451812

def bv2av(bv_str):
    """ return av_int """
    # http://api.bilibili.com/x/web-interface/archive/stat?bvid={}
    r=0
    for i in range(6):
        r+=V_MAP[bv_str[V_OFFSET[i]]]*58**i
    return (r-V_ADD)^V_XOR

def av2bv(av_int):
    """ return bv_str """
    av_int=(av_int^V_XOR)+V_ADD
    r=list("BV1  4 1 7  ")
    for i in range(6):
        r[V_OFFSET[i]]=V_TABLE[av_int//58**i%58]
    return "".join(r)

def req_get(url,headers={},proxies={},timeout=10.0, sleep=0.3):
    status_code = -1
    while status_code != 200:
        try:
            with eventlet.Timeout(timeout):
                req = requests.get(url,headers=headers, proxies=proxies)
        except:
            print("x retry!")
            time.sleep(sleep)
            continue
        status_code = req.status_code
    return req

def is_any_thread_alive(thread_L):
    return True in [t.is_alive() for t in thread_L]

""" Fetch vlist
# func:  fetch_vlist(mid)
# retn:  ---
# dump:  "./infos/{mid}-vlist.json"
"""

info_path = "./infos/"
vlist_fname = "{}-vlist.json".format(mid)

def fetch_vpage(mid, page, pagesize=100):
    av_url_body = "https://space.bilibili.com/ajax/member/getSubmitVideos?mid={}&page={}&pagesize={}"
    print("> Fetching mid {} page {}".format(mid,page))
    req  = req_get(av_url_body.format(mid,page,pagesize), headers=headers(), timeout=4.0, sleep=0.3)
    data = req.json()
    page_num = data["data"]["pages"]
    return data, page_num

def fetch_vlist(mid=mid):
    page, pagesize = 1, 100
    jsn, page_num = fetch_vpage(mid, page,pagesize)

    for i in range(2, page_num+1):
        time.sleep(0.4)
        tmp_jsn, _ = fetch_vpage(mid,i,pagesize)
        jsn["data"]["vlist"].extend(tmp_jsn["data"]["vlist"])

    if not os.path.exists(info_path):
        os.mkdir(info_path)
    with open(info_path+vlist_fname, mode="w", encoding="utf-8") as wf:
        data = jsn["data"]
        json.dump(jsn["data"], wf)

# fetch_vlist(mid)

""" Parse vlist
# func:  parse_vlist(mid)
# retn:  ---
# open:  "./infos/{mid}-vlist.json"
# dump:  "./infos/{mid}-vinfo.pkl"
         vinfo_L: list of dict (video_num x col_num)
            each row: {aid: *, created: *, title: *, pic_url: *, length: *}
            sorted by aid
"""

vinfo_fname = "{}-vinfo.pkl".format(mid)

def parse_vlist(mid=mid):
    with open(info_path+vlist_fname, mode="r", encoding="utf-8") as rf:
        data = json.load(rf)
    video_L = []
    cover_L = []
    for i,video in enumerate(data["vlist"]):
        # print("{:>3}/{} {:<10} {}  {}".format(i+1,len(data["vlist"]),video["aid"], datetime.datetime.fromtimestamp(int(video["created"])), video["title"]))
        vinfo_D = {}
        for key in ["aid", "title","created","length","pic"]:
            vinfo_D[key] = video[key]
        video_L.append(vinfo_D)

    video_L = sorted(video_L, key=lambda k:k["created"])
    for i,video in enumerate(video_L):
        print("{:>3}/{} {:>10} {}  {}".format(i+1,len(video_L), video["aid"], datetime.datetime.fromtimestamp(int(video["created"])), video["title"]))
    with open(info_path+vinfo_fname, "w") as wf:
        json.dump(video_L, wf)

# parse_vlist(mid)


""" Fetch replies
# func:  fetch_replies(mid)
# retn:  ---
# open:  "./infos/{mid}-vinfo.pkl"
# save:  "./replies/mid-{mid}/aid-{*}/reply-{*}-{size}.json"
"""

reply_url_next = "http://api.bilibili.com/x/v2/reply/main?oid={}&type=1&mode=2&next={}&ps={}"
reply_url_prev = "http://api.bilibili.com/x/v2/reply/main?oid={}&type=1&mode=2&prev={}&ps={}"

reply_path_body = "./replies/mid-"+str(mid)+"/aid-{:0>12}/"
floor_margin = 1000
video_cnt, total_video_cnt = -1, -1

def fetch_floors(aid,prev_floor=0,ps=1,video_cnt=-1,proxies={}):
    print("> {:>3}/{:>3} aid={:<10} prev={:<7} ps={:<4}".format(video_cnt, total_video_cnt,aid,prev_floor,ps))
    reply_path = reply_path_body.format(aid)

    t1 = time.time()
    if prev_floor==0:
        flr_fname = "reply-{:0>6}-{:0>4}.json".format(prev_floor,floor_margin)
    else:
        flr_fname = "reply-{:0>6}-{:0>4}.json".format(prev_floor,ps)

    if prev_floor == 0:
        req = req_get(reply_url_next.format(aid,floor_margin,floor_margin), headers=headers(), timeout=4.0, sleep=0.5)
    else:
        req = req_get(reply_url_prev.format(aid,prev_floor,ps), headers=headers(), timeout=4.0, sleep=0.5)

    t2 = time.time()

    status_flag = "+++" if req.status_code==200 else "xxx"
    print("{} {}  {}s".format(status_flag, req.status_code, round(t2-t1,1)))

    jsn = json.loads(req.content.decode("utf-8"))

    # Here often occurs: Keyerror: 'data' ...
    # Restart (several trials) the program solves it.
    # Still don't know why. Maybe the issue of home network.

    if not jsn["data"]["cursor"]["is_begin"]:
        with open(reply_path+flr_fname, "wb") as wf:
            wf.write(req.content)

    finfo_L = []
    for key in ["all_count","prev","next","is_begin","is_end"]:
        finfo_L.append(jsn["data"]["cursor"][key])

    return finfo_L

def fetch_replies(aid, is_overwrite=False, fetch_replies_sema=None, video_cnt=-1,proxies={}):
    if fetch_replies_sema:
        fetch_replies_sema.acquire()

    reply_path = reply_path_body.format(aid)
    if not os.path.exists(reply_path):
        os.makedirs(reply_path)

    old_prev_floor = 0
    page_floor_size = 1000

    if os.listdir(reply_path) == []:
        pass
    else:
        if is_overwrite or len(os.listdir(reply_path))<=1:
            shutil.rmtree(reply_path)
            os.makedirs(reply_path)
        else:
            # print(os.listdir(reply_path))
            os.remove(reply_path+os.listdir(reply_path)[-1])
            last_filename = os.listdir(reply_path)[-1]
            with open(reply_path+last_filename,mode="r",encoding="utf-8") as rf:
                jsn = json.load(rf)
            old_prev_floor = jsn["data"]["cursor"]["prev"]

    all_count, new_prev_floor, next_floor, is_begin, is_end = fetch_floors(aid, old_prev_floor,page_floor_size,video_cnt,proxies)

    # max_floor = 3500
    # while not (is_begin or new_prev_floor==old_prev_floor or new_prev_floor > max_floor):
    while not (is_begin or new_prev_floor==old_prev_floor):
        old_prev_floor = new_prev_floor
        time.sleep(0.2)
        all_count, new_prev_floor, next_floor, is_begin, is_end = fetch_floors(aid,new_prev_floor,page_floor_size,video_cnt,proxies)

    if fetch_replies_sema:
        fetch_replies_sema.release()

def fetch_all_video_replies(mid=mid,is_overwrite=False):
    global total_video_cnt
    vinfo_fname = "{}-vinfo.pkl".format(mid)
    with open(info_path+vinfo_fname, "r") as rf:
        video_L = json.load(rf)

    total_video_cnt = len(video_L)
    start_cnt = 0
    # for i, video in enumerate(reversed(video_L)[start_cnt:]):
    for i, video in enumerate(video_L[start_cnt:]):
        video_cnt = start_cnt+i+1
        t1 = time.time()
        print("Fetching  aid={:<10} {}".format(video["aid"], video["title"]))
        fetch_replies(video["aid"],is_overwrite=is_overwrite,video_cnt=video_cnt)
        t2 = time.time()
        print("=== {:>3}/{:>3} Elapsed time: {}s".format(video_cnt, total_video_cnt, round(t2-t1,1)))

# fetch_all_video_replies(mid=mid)

def fetch_all_video_replies_multi(video_L,is_overwrite=False):
    global video_cnt, total_video_cnt
    total_video_cnt = len(video_L)

    fetch_replies_sema = threading.BoundedSemaphore(5)

    start_cnt = 0
    thread_L = []
    for i, video in enumerate(video_L[start_cnt:]):
        video_cnt = start_cnt+i+1
        tmp_thread = threading.Thread(target=fetch_replies,args=(video["aid"],False,fetch_replies_sema,video_cnt))
        thread_L.append(tmp_thread)
    for tmp_thread in thread_L:
        tmp_thread.start()

    while is_any_thread_alive(thread_L):
        time.sleep(0)

""" Parse replies
# func:  parse_replies(mid)
# retn:  ---
# open:  "./replies/mid-{mid}/aid-{*}/reply-{*}-{size}.json"
# dump:  "./infos/{mid}-finfo.pkl"
         finfo_D: dict of list (1 x video_num)
            each key,val: {aid: flr_ct_L}
                flr_ct_L: 2d list (flr_num x 2)
                    each row: [flr_idx, ctime]
                        flr_num: total num of all floors
                        flr_idx: index of current floor
                        ctime:   timestamp of floor
"""

def parse_replies(mid=mid):
    root = "./replies/mid-{}/".format(mid)
    finfo_D = {}
    t0 = time.time()
    folder_L = os.listdir(root)[:]
    for i,folder in enumerate(folder_L):
        t1 = time.time()
        aid = int(re.findall(r"aid-(\d+)",folder)[0])
        finfo_L = []
        for fname in os.listdir(root+folder)[:]:
            with open(join_path(root,folder,fname),"r",encoding="utf-8") as rf:
                jsn = json.load(rf)
                for reply in jsn["data"]["replies"]:
                    finfo_L.append([reply["floor"],reply["ctime"]])
        finfo_L = sorted(finfo_L, key=lambda v:v[0])
        finfo_D[aid]= finfo_L
        print("{:>3}/{:<3} | {:<10} {:<6} | {}s".format(i+1, len(folder_L), aid, len(finfo_L), round(time.time()-t1,1)))

    with open(info_path+"finfo.pkl", "wb") as wf:
        pickle.dump(finfo_D, wf)
    print("Total elapsed time: {}s".format(round(time.time()-t0,1)))

# parse_replies(mid)

""" Accumulate replies
# func:  accum_replies(mid)
# retn:  ---
# open:  "./infos/{mid}-finfo.pkl"
# dump:  "./infos/{mid}-tinfo.pkl", "./infos/{mid}-ninfo.pkl"
        tinfo: list of ctime (1 x ct_group_cnt)
        ninfo: 2d list (video_num x ct_group_cnt)
            each row: list, accumulate floor nums of all ctime groups
"""


""" Sort replies with ctime
# func:  sort_replies(mid)
# retn:  ---
# open:  "./infos/{mid}-tinfo.pkl", "./infos/{mid}-ninfo.pkl"
# dump:  "./infos/{mid}-sinfo.pkl"
         sinfo: 2d list (ct_group_cnt x k)
            each row: list (1 x k), top k aids ranked by accumulated floor nums at each ctime group
"""


""" [Not in this file] Animation """
