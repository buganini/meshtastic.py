# Hardware
* FT232H + SX127x/SX126x
![Hardware](images/hardware.jpg)

## Tested with:
    * Ra-01H (SX1276)
    * Ra-01SH (SX1262)

## Wiring
FT232H doesn't support interrupt so all we use are

* 3V3
* GND
* nRST
* CS
* CLK
* MI
* MO


# Initialization
```
pip3 install -r requirements.txt
```

# Run
```
python3 main.py # GUI
python3 main.py --textual # TUI
```

# TODO
* CAD
