# -*- coding: utf-8 -*-
"""
greenbox
使用mmap共享内存通信
对于写者，需要
1）创建一个greenbox
2）往greenbox中写入信息
3）关闭greenbox
写无阻碍，必须成功

对于读者，需要
1）连接一个greenbox
2）从greenbox中读出信息
3）断开与greenbox的连接
读可以失败

缓冲区文件采用内存文件系统/dev/shm/greenbox/xxx.gb

适用场景:
1)一般情况下读者的速度要高于写者，一旦写者产生了过多的数据能够将会丢失掉部分
2)传输的内容大小较为一致，能够充分利用每个缓冲区
"""
import mmap
import time
import os
class Greenbox4writer:
    def __init__(self, name, bs, count):
        """
        name: greenbox 缓冲区的名字，也是唯一的区分id
        bs：blocksize, xxx bytes 每个block的大小
        count：number of block 需要的block的数目
        bs,count共同决定了greenbox的大小，基本是缓冲区的大小
        每个缓冲区有两个标志位
        state位：若为's'表示writer正在操作此缓冲区，若为'0x00'表示writer不在
        pass位：循环在1 和 0 中变化，writer每经过一次变化一次
        """
        if os.path.exists('/dev/shm/greenbox'):
            if os.path.isfile('/dev/shm/greenbox'):
                os.remove('/dev/shm/greenbox')
                os.mkdir('/dev/shm/greenbox')
            if os.path.exists('/dev/shm/greenbox/%s.gb'%(name)):
                os.remove('/dev/shm/greenbox/%s.gb'%(name))
            os.system('dd if=/dev/zero of=/dev/shm/greenbox/%s.gb bs=%s count=%s'%(name, bs+2, count))
        else:
            os.mkdir('dev/shm/greenbox')
            os.system('dd if=/dev/zero of=/dev/shm/greenbox/%s.gb bs=%s count=%s'%(name, bs+2, count))

        self.count=count
        self.bs=bs
        self.pos=0  #pos [0..count-1]

        size=(bs+2)*count
        with open('/dev/shm/greenbox/%s.gb'%(name), "r+b") as f:
            self.mm = mmap.mmap(f.fileno(), length=size, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ|mmap.PROT_WRITE, offset=0)

        offset=0
        self.mm[offset]='s'
        self.mm[offset+1]='\x01'

    def close(self):
        self.mm.close()
        os.remove('/dev/shm/greenbox/%s.gb'%(name))

    def put(self, msg):
        """
        如果输入的字符串类型及大小不符合要求，失败，返回False
        成功，则返回True

        流程
        1写内容
        2变化被写缓冲区的pass位
        3将下一个缓冲区的state位置为's'
        4将背写缓冲区的state位置为'\x00'

        """
        if type(msg) is not str:
            return False
        if len(msg)>self.bs-1:  #should add '\n' to the end
            return False

        offset0=(self.bs+2) * self.pos

        #step1: write message
        offset=offset0+2 #2 bytes for mark
        self.mm[offset:offset+len(msg)]=msg
        self.mm[offset+len(msg)]='\n'

        #step2: change marks
        newpos = (self.pos+1)%self.count
        offset1=(self.bs+2) * newpos
        self.mm[offset0+1]= chr(ord(self.mm[offset0+1]) ^1) #pass位
        self.mm[offset1]='s' #state位
        self.mm[offset0]='\x00' #state位
        self.pos=newpos
        
        return True
        


class Greenbox4reader:
    def __init__(self, name, bs, count):
        """
        name: greenbox 缓冲区的名字，也是唯一的区分id
        bs：blocksize, xxx bytes
        count：number of block
        每个缓冲区有两个标志位
        state位：若为's'表示writer正在操作此缓冲区，若为'0x00'表示writer不在
        pass位：循环在True 和 False 中变化，writer每经过一次变化一次

        如果文件不错在或者大小不合适，抛出异常'greenbox buffer is not ready, check whether the writer has create this greenbox'
        """
        if not os.path.exists('/dev/shm/greenbox/%s.gb'%(name)):
            raise Exception('greenbox buffer is not ready, check whether the writer has create this greenbox')
        if os.path.getsize('/dev/shm/greenbox/%s.gb'%(name)) != (bs+2)*count :
            raise Exception('greenbox buffer is not ready, check whether the writer has create this greenbox')

        self.count=count
        self.bs=bs
        self.pos=0  #pos [0..count-1]

        size=(bs+2)*count
        with open('/dev/shm/greenbox/%s.gb'%(name), "r+b") as f:
            self.mm = mmap.mmap(f.fileno(), length=size, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ, offset=0)


    def close(self):
        self.mm.close()


    def get(self):
        """
        非阻塞取出一行，
        如果失败，返回False
        如果成功，返回取得的字符串（包含最后的'\\n'）


        流程
        1读取pass位，记为p1
        2读内容
        3再判断state位，如果被置位为's'，读失败
        4判断pass位置，记为p2，如果p1<>p2，读失败

        即操作顺序是p1,read,s,p2
        
        """
        offset0=(self.bs+2) * self.pos
        
        p1=self.mm[offset0+1]

        self.mm.seek(offset0+2,0)
        msg=self.mm.readline()
        msg=msg[0:len(msg)-1]

        s=self.mm[offset0]
        if s=='s':
            return False

        p2=self.mm[offset0+1]
        if p1<>p2:
            return False

        self.pos = (self.pos+1)%self.count
        return msg


        



        

        



        
