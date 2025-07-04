sudo apt update

# Can't get Python3.8 directly, so compile it
# TODO: Check if autoremove is still needed or not
sudo apt-get install -y build-essential libssl-dev zlib1g-dev libbz2-dev \
                        libreadline-dev libsqlite3-dev wget curl llvm \
                        libncurses5-dev libncursesw5-dev xz-utils tk-dev \
                        libpcap-dev libncurses-dev autoconf automake libtool pkg-config \
                        libffi-dev liblzma-dev python3-openssl git

#Get Python3.8 directly
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install python3.8 python3.8-venv -y
echo "alias python=python3.8" >> .bashrc
source .bashrc

# Compiling Python from source. Still buggy!!!
#mkdir ~/python38
#cd ~/python38
#wget https://www.python.org/ftp/python/3.8.16/Python-3.8.16.tgz
#tar -xf Python-3.8.16.tgz
#cd Python-3.8.16

#./configure --enable-optimizations
#make -j$(nproc)
#sudo make install

#cd ../..
#echo "alias python=python3.8" >> .bashrc
#source .bashrc

# Install iftop (for network monitoring)
#sudo apt-get install iftop

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh && 
    sh get-docker.sh && 
    sudo usermod -aG docker ubuntu
sudo systemctl start docker

# Create Python env
python3.8 -m venv build_detock
source build_detock/bin/activate

sudo apt install net-tools
sudo apt install dstat -y
sudo apt install cmake build-essential pkg-config -y

# If you want to use the default iftop
#sudo apt install iftop

# Compile custom iftop
#cd iftop
#chmod +x bootstrap 
#./bootstrap
#chmod +x configure 
#./configure
#make
#sudo make install
#cd ..

# Setups specific for Detock
cd Detock

# Install libraries
python3.8 -m pip install --upgrade pip
pip install -r tools/requirements.txt

# Start monitoring script
# TODO: Check that this also really launches iftop (otherwise add iftop at the end here)
#nohup python3 aws/monitor_util.py &