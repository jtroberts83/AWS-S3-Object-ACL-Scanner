import threading
from queue import Queue
import time
import shutil
import boto3
import json
from threading import Lock

keycounter=0
errorcounter=0
errorcounter2=0
S3errorcounter=0
S3validbuckets=0
openfilescounter=0

#################################
##   Set the following Vars    ##
#################################
roleToAssume = 'SomeRoleName'
account = 'AccountNumber'



stsClient = boto3.client('sts')
roleArn=("arn:aws:iam::%s:role/%s" % (account,roleToAssume))
response = stsClient.assume_role(
        RoleArn=roleArn,
        RoleSessionName='S3_Object_ACL_CheckerAssumed',
        DurationSeconds=3600,
    )
AccessKey = response['Credentials']['AccessKeyId']
SecretAccessKey = response['Credentials']['SecretAccessKey']
SessionToken = response['Credentials']['SessionToken']
print('Access Key Aquired -  ',AccessKey)
all_users = 'http://acs.amazonaws.com/groups/global/AllUsers'
s3 = boto3.client('s3',aws_access_key_id=AccessKey,aws_secret_access_key=SecretAccessKey,aws_session_token=SessionToken)

allbuckets = (s3.list_buckets())['Buckets']
#print(allbuckets)
bucketnames = []
lockedbuckets = []
for bucket in allbuckets:
        bucketnames.append(bucket['Name'])
#print(bucketnames)

print_lock = threading.Lock()
out_lines = []
def update(key):
    with print_lock:
        print("Starting thread : {}".format(threading.current_thread().name))
    global keycounter
    keycounter += 1
    #print('Hello')
    #key,bucketname = combinedvars.split("-")
    try:
        acl = s3.get_object_acl(Bucket=key[1],Key=key[0])

        #return acl
        for grant in acl['Grants']:
            #print(grant)
            try:
                grantinfo = grant['Grantee']['URI']
                #print(grantinfo)
                if grantinfo == all_users:
                    global openfilescounter
                    openfilescounter += 1
                    print("OPEN TO WORLD- %s / %s " % (bucketname, key))
                    out_lines.append("OPEN TO WORLD- %s / %s " % (bucketname, key))
            except KeyError:
                nothing = 0
                global errorcounter
                errorcounter += 1

    except:
        global errorcounter2
        errorcounter2 += 1
    with print_lock:
        print("Finished thread : {}".format(threading.current_thread().name))

def process_queue():
    while True:
        key = key_queue.get()
        update(key)
        key_queue.task_done()

key_queue = Queue()

for i in range(100):
    t = threading.Thread(target=process_queue)
    t.daemon = True
    t.start()

start = time.time()

for bucketname in bucketnames:

    try:
        allobjects = s3.list_objects(Bucket=bucketname)
        #print(allobjects)
        allkeys =[]
        for s3object in allobjects['Contents']:
            somevar = [s3object['Key'],bucketname]
            key_queue.put(somevar)
        S3validbuckets += 1
    except:
        S3errorcounter += 1
        lockedbuckets.append(bucketname)
    key_queue.join()

print("Execution time (Minutes)= {0:.5f}".format((time.time() - start)/60))
out_string = '\n'.join(out_lines)
out_filename = 'myfile.txt'
with open(out_filename, 'w') as outf:
    outf.write(out_string)
outf.close()
print(out_string)
print("Found %s S3 objects open to the world.  \n Processed %s S3 Keys in %s buckets with %s Object Access Denied Errors, %s Read Grant Access and %s Bucket Denied Errors" % (openfilescounter,keycounter,S3validbuckets,errorcounter,errorcounter2,S3errorcounter))
print("\n The following Buckets Have a Deny Statement blocking %s role access:\n" % roleToAssume)
for lockedbucket in lockedbuckets:
    print(lockedbucket)
