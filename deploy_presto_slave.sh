#/usr/bin/bash

echo "stopping the Presto server"
/usr/bin/supervisorctl stop presto &>/dev/null

echo "Downloading latest release"
aws s3 cp s3://adroll-test-sandbox-2/presto-upgrade-test/presto-server-builds/presto-server.tar.gz . &>/dev/null

echo "Extracting the tarball"
tar xvzf presto-server.tar.gz &>/dev/null

echo "Setting up"
rm -rf /opt/presto
mv presto-server-* presto
mv presto /opt/
cp -r slave/etc /opt/presto/

echo "Starting the Presto server"
/usr/bin/supervisorctl start presto &>/dev/null
