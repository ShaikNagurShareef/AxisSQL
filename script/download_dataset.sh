#!/bin/bash

#################### BIRD test set (not publicly downloadable) ##########################
# The BIRD Bench test set (test.json + test_databases/) is held out and not hosted at a
# public URL. To obtain it and get official test-set scores (EX / R-VES), email
# bird.bench23@gmail.com and follow BIRD's Submission Guideline. Once received, place it at
# data/bird/test/test.json and data/bird/test/test_databases/{db_id}/{db_id}.sqlite, then set
# split = "test" in the [dataset] block. See README "BIRD Bench Test Set Submission".

#################### download BIRD dev dataset ##########################
# create directory
mkdir -p data/bird
cd data/bird

# download dataset
wget https://bird-bench.oss-cn-beijing.aliyuncs.com/dev.zip
unzip dev.zip

# rename dev_20240627 to dev
mv dev_20240627 dev

# unzip databases
cd dev
unzip dev_databases.zip

