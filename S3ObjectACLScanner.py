import threading
from queue import Queue
import time
import shutil
import boto3
import json
from threading import Lock

### Configurable vars
threadcount = 100

# Read active AWS account by open session & role
account = boto3.client('sts').get_caller_identity().get('Account')

# Load bucket inventory file
inventory = f"inventory/phase1-{account}.list"
file = open(inventory, 'r')
f = file.read()
bucketnames = f.splitlines()

# Set output
out_filename = f"S3-Public-Objects-{account}.txt"

### Counters used for stats at the end of script run
keycounter=0
errorcounter=0
errorcounter2=0
S3errorcounter=0
S3validbuckets=0
openfilescounter=0

### Specifies the AllUsers group to look for in the objects ACLs
all_users = 'http://acs.amazonaws.com/groups/global/AllUsers'

s3 = boto3.client('s3')

lockedbuckets = []
print_lock = threading.Lock()
out_lines = []

###  update function which cycles through each key in the Queue checking its ACL permissions
def update(key):
    with print_lock:
        print("Starting thread : {}".format(threading.current_thread().name))
    global keycounter
    keycounter += 1
    
    ###  Try to get the objects ACL
    try:
        acl = s3.get_object_acl(Bucket=key[1],Key=key[0])

        ###  Loop through each Grant found on the object
        for grant in acl['Grants']:
            #print(grant)
            try:
                grantinfo = grant['Grantee']['URI']
                #print(grantinfo)
                
                ###  If the Grant found is the All Users Grant then add it to the log file and print info
                if grantinfo == all_users:
                    global openfilescounter
                    openfilescounter += 1
                    print("OPEN TO WORLD- %s / %s " % (bucketname, key))
                    out_lines.append("OPEN TO WORLD- %s / %s " % (bucketname, key))
            except KeyError:
                global errorcounter
                errorcounter += 1
    ### If it errors out trying to get the objects ACL
    except:
        global errorcounter2
        errorcounter2 += 1
    with print_lock:
        print("Finished thread : {}".format(threading.current_thread().name))

### Process the Queue of S3 keys for the bucket
def process_queue():
    while True:
        key = key_queue.get()
        update(key)
        key_queue.task_done()

#### Creates a Queue which will hold a key/value pair for keyname,bucketname which will get passed for multithreading
key_queue = Queue()


### Here is where it creates multiple threads.  In this example it uses 100 threads.  Adjust for your instance type/resources
for i in range(threadcount):
    t = threading.Thread(target=process_queue)
    t.daemon = True
    t.start()

### Gets the start time to use for total time duration of script
start = time.time()

### Loop through each bucket in the account to check its objects
for bucketname in bucketnames:

    try:
        allobjects = s3.get_paginator('list_objects')
        for p in allobjects.paginate(Bucket=bucketname):
            #print(p)
            allkeys =[]
            for s3object in p['Contents']:
                somevar = [s3object['Key'],bucketname]
                key_queue.put(somevar)
            S3validbuckets += 1
    except:
        S3errorcounter += 1
        lockedbuckets.append(bucketname)
    key_queue.join()

print("Execution time (Minutes)= {0:.5f}".format((time.time() - start)/60))
out_string = '\n'.join(out_lines)

### Write the open S3 keys to the out_filename file
with open(out_filename, 'w') as outf:
    outf.write(out_string)
outf.close()

print(out_string)
print("Found %s S3 objects open to the world.  \n Processed %s S3 Keys in %s buckets with %s Object Access Denied Errors, %s Read Grant Access and %s Bucket Access Denied OR Bucket Empty Errors" % (openfilescounter,keycounter,S3validbuckets,errorcounter,errorcounter2,S3errorcounter))
print("\n The following Buckets Have a Deny Statement blocking %s role access OR they are empty:\n" % roleToAssume)

### Print out each key's info that is Public
for lockedbucket in lockedbuckets:
    print(lockedbucket)
