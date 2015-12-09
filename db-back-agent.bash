#!/bin/bash
#/***************************************************************************
# * This software is licensed as described in the file COPYING, which
# * you should have received as part of this distribution. 
# *
# * You may opt to use, copy, modify, merge, publish, distribute and/or sell
# * copies of the Software, and permit persons to whom the Software is
# * furnished to do so, under the terms of the COPYING file.
# *
# ***************************************************************************/

source back.conf
export OS_USERNAME=$TENANT_USERNAME
export OS_TENANT_NAME=$TENANT_USERNAME
export OS_PASSWORD=$TENANT_PASSWD
export OS_AUTH_URL=http://210.14.69.69:5000/v2.0/
export OS_REGION_NAME=RegionOne
export BACKUP_DATE=$(date +"%Y%m%d")
export EXPIRE_BACKUP_DATE=$(date --date="$EXPIRE_BACK_DB_DAYS days ago" +"%Y%m%d")
export CURRENT_DIR=$(cd `dirname $0` && pwd)

mysqldump -u $DB_USERNAME -p $DB_PASSWD $DB_NAME > $BACK_DIR/$DB_NAME.$BACKUP_DATE

cd $BACK_DIR
tar czf $DB_NAME-$BACKUP_DATE.tar.gz $DB_NAME-$BACKUP_DATE
if [ $? -ne 1 ]; then
	#remove expire database in cloud backup
	#todo
        python upload.py $BACK_DIR/$DB_NAME.$BACKUP_DATE $BACK_DIR/$DB_NAME.$EXPIRE_BACKUP_DATE	$ADMIN_EMAIL
	#send the backup to cloud backup
	#todo
fi
