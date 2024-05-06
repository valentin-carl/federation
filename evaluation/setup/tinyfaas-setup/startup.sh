#!/bin/sh

sudo apt-get update
sudo apt-get install -y unzip zip build-essential # this should contain `make`

# install golang
wget https://go.dev/dl/go1.22.2.linux-amd64.tar.gz
sudo tar -C /usr/local -xzf go1.22.2.linux-amd64.tar.gz
echo "PATH=$PATH:/usr/local/go/bin" >> $HOME/.bashrc

# make go available for sudo
echo 'Defaults        secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin:/usr/local/go/bin"' | sudo tee /etc/sudoers.d/spath

# install docker
# add Docker's official GPG key:
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
# add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
# install docker
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
# verify installation was successful
sudo docker run hello-world
# enable current user to access docker without `sudo`
sudo groupadd docker
sudo usermod -aG docker "$USER"
newgrp docker
# now `docker run hello-world` without `sudo` to verify
docker run hello-world

# install tinyFaaS
mkdir /app
cd /app
sudo wget https://github.com/OpenFogStack/tinyFaaS/archive/refs/heads/main.zip
sudo unzip main.zip

## to run tinyFaaS, do this:
## tinyFaaS, make, and Docker don't play together nicely out of the box because of some permissions stuff
## so just use root and it works
#sudo su
#cd /app/tinyFaaS-main
#sudo make > /var/log/tinyfaas.log 2>&1 &
