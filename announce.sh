#! /bin/bash
#http GET http://localhost:5000/announce info_hash==12345678901234567890 peer_id==ABCDEFGHIJKLMNOPQRST ip==255.255.255.255 port==6881 uploaded==0 downloaded==1234 left==98765 event==stopped
#http GET http://localhost:5000/announce info_hash==12345678901234567890 peer_id==ABCDEFGHIJKLMNOPQRST ip==255.255.255.255 port==6881 uploaded==0 downloaded==1234 left==98765 event==completed
http GET http://localhost:5000/announce info_hash==12345678901234567890 peer_id==ABCDEFGHIJKLMNOPQRST ip==255.255.255.255 port==6881 uploaded==0 downloaded==1234 left==98765 
