#!/bin/sh

# python makecard-boost.py --name VBS --input ./config/input_UL_2018-fes.yaml --era 2018 --variable gnn_score --channel  vbs-DY  --rebin=10 
#python makecard-boost.py --name VBS --input ./config/input_UL_2018-fes.yaml --era 2018 --variable gnn_score --channel  vbs-TT  --rebin=10
python makecard-boost.py --name VBS --input ./config/input_UL_2018-fes.yaml --era 2018 --variable gnn_score --channel  vbs-EM  --rebin=50  
python makecard-boost.py --name VBS --input ./config/input_UL_2018-fes.yaml --era 2018 --variable gnn_score --channel  vbs-3L  --rebin=50 
python makecard-boost.py --name VBS --input ./config/input_UL_2018-fes.yaml --era 2018 --variable gnn_flat  --channel  vbs-SR  --rebin=10 --dd=True
#python makecard-boost.py --name VBS --input ./config/input_UL_2018-fes.yaml --era 2018 --variable gnn_score  --channel  vbs-SR  --rebin=10 

python makecard-boost.py --name VBS --input ./config/input_UL_2017-fes.yaml --era 2017 --variable gnn_score --channel  vbs-EM  --rebin=50 
#python makecard-boost.py --name VBS --input ./config/input_UL_2017-fes.yaml --era 2017 --variable gnn_score --channel  vbs-TT  --rebin=10 
# python makecard-boost.py --name VBS --input ./config/input_UL_2017-fes.yaml --era 2017 --variable gnn_score --channel  vbs-DY  --rebin=10 
python makecard-boost.py --name VBS --input ./config/input_UL_2017-fes.yaml --era 2017 --variable gnn_score --channel  vbs-3L  --rebin=50 
python makecard-boost.py --name VBS --input ./config/input_UL_2017-fes.yaml --era 2017 --variable gnn_flat  --channel  vbs-SR  --rebin=10 --dd=True
#python makecard-boost.py --name VBS --input ./config/input_UL_2017-fes.yaml --era 2017 --variable gnn_score  --channel  vbs-SR  --rebin=10 

# python makecard-boost.py --name VBS --input ./config/input_UL_2016-fes.yaml --era 2016 --variable gnn_score --channel  vbs-EM  --rebin=50 
# #python makecard-boost.py --name VBS --input ./config/input_UL_2016-fes.yaml --era 2016 --variable gnn_score --channel  vbs-TT  --rebin=10
# # python makecard-boost.py --name VBS --input ./config/input_UL_2016-fes.yaml --era 2016 --variable gnn_score --channel  vbs-DY  --rebin=10
# python makecard-boost.py --name VBS --input ./config/input_UL_2016-fes.yaml --era 2016 --variable gnn_score --channel  vbs-3L  --rebin=50 
# python makecard-boost.py --name VBS --input ./config/input_UL_2016-fes.yaml --era 2016 --variable gnn_flat  --channel  vbs-SR  --rebin=10 --dd=True
# #python makecard-boost.py --name VBS --input ./config/input_UL_2016-fes.yaml --era 2016 --variable gnn_score  --channel  vbs-SR  --rebin=10

# python makecard-boost.py --name VBS --input ./config/input_UL_2016APV-fes.yaml --era 2016APV --variable gnn_score --channel  vbs-EM  --rebin=50 
# #python makecard-boost.py --name VBS --input ./config/input_UL_2016APV-fes.yaml --era 2016APV --variable gnn_score --channel  vbs-TT  --rebin=10
# # python makecard-boost.py --name VBS --input ./config/input_UL_2016APV-fes.yaml --era 2016APV --variable gnn_score --channel  vbs-DY  --rebin=10
# python makecard-boost.py --name VBS --input ./config/input_UL_2016APV-fes.yaml --era 2016APV --variable gnn_score --channel  vbs-3L  --rebin=50 
# python makecard-boost.py --name VBS --input ./config/input_UL_2016APV-fes.yaml --era 2016APV --variable gnn_flat  --channel  vbs-SR  --rebin=10 --dd=True

python3 makecard-boost-2016combined.py --channel vbs-3L --variable gnn_score --rebin 50
python3 makecard-boost-2016combined.py --channel vbs-EM --variable gnn_score --rebin 50
python3 makecard-boost-2016combined.py --channel vbs-SR --variable gnn_flat --rebin 10 --dd=True
