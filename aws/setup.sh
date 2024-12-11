sudo apt update

# Can't get Python3.8 directly, so compile it
sudo apt-get install -y build-essential libssl-dev zlib1g-dev libbz2-dev \
                        libreadline-dev libsqlite3-dev wget curl llvm \
                        libncurses5-dev libncursesw5-dev xz-utils tk-dev \
                        libffi-dev liblzma-dev python3-openssl git

mkdir ~/python38
cd ~/python38
wget https://www.python.org/ftp/python/3.8.16/Python-3.8.16.tgz
tar -xf Python-3.8.16.tgz
cd Python-3.8.16

./configure --enable-optimizations
make -j$(nproc)
sudo make install

echo "alias python=python3.8" >> .bashrc
source .bashrc

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh && 
    sh get-docker.sh && 
    sudo usermod -aG docker ubuntu
sudo systemctl start docker

# Create Python env
cd ../..
python3.8 -m venv build_detock
source build_detock/bin/activate

sudo apt install net-tools
sudo apt install dstat -y
sudo apt install cmake build-essential pkg-config -y

# Setups specific for Detock
cd Detock

# Install libraries
python3.8 -m pip install --upgrade pip
pip install psutil
pip install -r tools/requirements.txt

# Start monitoring script
#python aws/monitor_util.py &