import boto3

account = boto3.client('sts').get_caller_identity().get('Account')
inventory = f"inventory/phase1-{account}.list"

file = open(inventory, 'r')
f = file.read()
bucketnames = f.splitlines()

for bucket in bucketnames:
  print(bucket)

lockedbuckets = []

print(bucketnames)
