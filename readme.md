# VIM4 & 128x32 Oled Display
**NOTE:** follow [OEM Link](https://docs.khadas.com/products/sbc/vim4/applications/gpio/i2c#tab__vim4) to enable i2c.  
**NOTE:** `i2c` address is muxed and might be other than specified, perform `i2cdetect -l` and then `i2cdetect -y 4` so see if there are `i2c` address available for your OLED Display.  
**NOTE:** some `i2c` OLED displays have their SCL/SDA mislabeled, if you are not getting address from OLED while its connected try swapping following:  
display: `SCL -> SDA` VIM4  
display: `SDA -> SCL` VIM4  

This is aimed to be also easy to modify for 128x64 oled display 

if you planning to install manually execute the following:
**NOTE:** You will have to install requirements
**TODO:** have requirements list

```bash
git clone https://github.com/username/repository-name

cd repository-name
sudo cp oled-netinfo.yaml /etc/oled-netinfo.yaml
sudo cp oled_netinfo.py /usr/local/bin/oled_netinfo.py
sudo chmod +x /usr/local/bin/oled_netinfo.py

sudo systemctl daemon-reload
sudo systemctl enable oled-netinfo.service
sudo systemctl start oled-netinfo.service
sudo systemctl status oled-netinfo.service
```

**TODO:** create install.sh script 
