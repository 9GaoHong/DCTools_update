import yaml
import os
import json
import gzip
import pickle
import argparse
import dctools
import hist
import matplotlib.pyplot as plt
from dctools import plot_fit as plotter
from typing import Any, IO
import numpy as np

class config_input:
    def __init__(self, cfg):
        self._cfg = cfg 
    
    def __getitem__(self, key):
        v = self._cfg[key]
        if isinstance(v, dict):
            return config_input(v)

    def __getattr__(self, k):
        try:
            v = self._cfg[k]
            if isinstance(v, dict):
                return config_input(v)
            return v
        except:
            return None
    def __iter__(self):
        return iter(self._cfg)



class config_loader(yaml.SafeLoader):
    """YAML Loader with `!include` constructor."""
    def __init__(self, stream: IO) -> None:
        """Initialise Loader."""
        try:
            self._root = os.path.split(stream.name)[0]
        except AttributeError:
            self._root = os.path.curdir
        super().__init__(stream)


def construct_include(loader: config_loader, node: yaml.Node) -> Any:
    """Include file referenced at node."""
    filename = os.path.abspath(os.path.join(loader._root, loader.construct_scalar(node)))
    extension = os.path.splitext(filename)[1].lstrip('.')

    with open(filename, 'r') as f:
        if extension in ('yaml', 'yml'):
            return yaml.load(f, config_loader)
        elif extension in ('json', ):
            return json.load(f)
        else:
            return ''.join(f.readlines())

yaml.add_constructor('!include', construct_include, config_loader)

def main():
    parser = argparse.ArgumentParser(description='The Creator of Combinators')
    parser.add_argument("-i"  , "--input"   , type=str , default="./config/input_UL_2018_timgad-vbs.yaml")
    parser.add_argument("-v"  , "--variable", type=str , default="nnscore")
    parser.add_argument("-y"  , "--era"     , type=str , default='2018')
    parser.add_argument("-c"  , "--channel" , nargs='+', type=str)
    parser.add_argument("-s"  , "--signal"  , nargs='+', type=str)
    parser.add_argument('-n'  , "--name"    , type=str , default='')
    parser.add_argument('-p'  , "--plot"    , action="store_true")
    parser.add_argument('--rebin', type=int, default=1, help='rebin')
    parser.add_argument("--bins", 
            type=lambda s: [float(item) for item in s.split(',')], 
            help='input a comma separated list. ex: --bins="-1.2,0,1.2"'
    )
    parser.add_argument('--blind', action='store_true', help='blinding the channel')
    parser.add_argument('--checksyst', action='store_true')
    parser.add_argument("-d" ,  '--dd', type=bool , default=False )

    options = parser.parse_args()
    config = dctools.read_config(options.input)

    print(f'making: {options.channel} : {options.variable} : {options.era}')

    if len(options.channel) == 1:
        options.channel = options.channel[0]
    
    # make datasets per prcess
    datasets = {}
    signal = ""

    if options.name=='':
        options.name == options.channel
        
        
    datasets:Dict = dict()
    for name in config.groups:
        histograms = dict(
            filter(
                lambda _n: _n[0] in config.groups[name].processes,
                config.boosthist.items()
            )
        )
        
        p = dctools.datagroup(
            histograms = histograms,
            ptype      = config.groups[name].type,
            observable = options.variable,
            name       = name,
            xsections  = config.xsections,
            channel    = options.channel,
            luminosity = config.luminosity.value,
            rebin      = options.rebin,
            era        = options.era
        )
        
        datasets[p.name] = p
        if p.ptype == "signal":
            signal = p.name


    if options.plot:
        _plot_channel = plotter.add_process_axis(datasets)
        pred = _plot_channel.project('process','systematic', options.variable)[:hist.loc('data'),:,:]
        data = _plot_channel[{'systematic':'nominal'}].project('process',options.variable)[hist.loc('data'),:] 

        plt.figure(figsize=(6,7))
        ax, bx = plotter.mcplot(
            pred[{'systematic':'nominal'}].stack('process'),
            data=None if options.blind else data, 
            syst=pred.stack('process'),
        )
        
        try:
            sig_ewk = _plot_channel[{'systematic':'nominal'}].project('process', variable)[hist.loc('VBSZZ2l2nu'),:]   
            sig_qcd = _plot_channel[{'systematic':'nominal'}].project('process', variable)[hist.loc('ZZ2l2nu'),:]   
            sig_ewk.plot(ax=ax, histtype='step', color='red')
            sig_qcd.plot(ax=ax, histtype='step', color='purple')
        except:
            pass
    
        ymax = np.max([line.get_ydata().max() for line in ax.lines if line.get_ydata().shape[0]>0])
        ymin = np.min([line.get_ydata().min() for line in ax.lines if line.get_ydata().shape[0]>0])
    
        ax.set_ylim(0.001, 100*ymax)
        ax.set_title(f"channel {options.channel}: {options.era}")

        ax.set_yscale('log')
        plt.savefig(f'plot-{options.channel}-{options.variable}-{options.era}.pdf')


    if options.checksyst:        
        _plot_channel = plotter.add_process_axis(datasets)
        pred = _plot_channel.project('process','systematic', options.variable)[:hist.loc('data'),:,:]
        data = _plot_channel[{'systematic':'nominal'}].project('process',options.variable)[hist.loc('data'),:] 
        plotter.check_systematic(
            pred[{'systematic':'nominal'}].stack('process'),
            syst=pred.stack('process'),
            plot_file_name=f'check-sys-{options.channel}-{options.era}'
        )

    card_name = options.channel+options.era

    card = dctools.datacard(
        name = signal if len(options.name)==0 else options.name,
        channel= card_name
    )
    card.shapes_headers()

    def _scale_dd_uncertainty(shape_tuple, year_tag):
        """
        Rescale DD ratio up/down shapes so their integrals match the
        dedicated MET-bin uncertainties used when deriving the weights.
        """
        if not isinstance(shape_tuple, tuple) or len(shape_tuple) != 2:
            return shape_tuple
        up_hist, down_hist = shape_tuple
        if up_hist is None or down_hist is None:
            return shape_tuple

        year_str = str(year_tag)
        if '2016' in year_str:
            low_up, low_down = 1.086, 0.924
        elif year_str in ('2017', '2018'):
            low_up, low_down = 1.019, 0.983
        else:
            return shape_tuple

        def _apply(hist_obj, factor):
            return hist_obj * factor

        scaled_up = _apply(up_hist, low_up)
        scaled_down = _apply(down_hist, low_down)
        return (scaled_up, scaled_down)
    
    data_obs = datasets.get("data").get("nominal")
    
    card.add_observation(data_obs)

    for _, p in datasets.items():
        if len(p.to_boost().shape) == 0:
            print(f"--> histogram for the process {p.name} is empty !")
            continue
        nominal_hist = p.get("nominal")
        if nominal_hist.sum().value == 0:
            print(f"--> histogram for the process {p.name} is empty !")
            continue
        if p.ptype=="data":
            continue

        print(p.name)
        
        if not card.add_nominal(p.name, nominal_hist, p.ptype): continue
        year = options.era.replace('APV','')
        era_s = options.era.replace('APV','preVFP')
        if "DY" in p.name and options.dd:
            dd_shape = p.get(f"dataDrivenDYRatio_{year}")
            dd_shape = _scale_dd_uncertainty(dd_shape, year)
            card.add_shape_nuisance(p.name, f"CMS_SMP23001_DY_dd_uncert_{year}", dd_shape, symmetrise=False)
            # card.add_auto_stat()
            continue
        

        if 'WW' not in p.name and 'WZ' not in p.name and 'DY' not in p.name and 'Top' not in p.name:
            card.add_log_normal_lumi(p.name, f"lumi_{year}", config.luminosity.uncer)
            card.add_log_normal_lumi(p.name, f"lumi_13TeV_correlated", config.luminosity.uncer_correlated)
            if "16" not in year:
                card.add_log_normal_lumi(p.name, f"lumi_13TeV_1718", config.luminosity.uncer_correlated1718)
            
        if "18" in year:
            card.add_shape_nuisance(p.name, f"CMS_HEM_2018"  , p.get("HEM"), symmetrise=False)
        # interference between QCD and EWK
        card.add_log_normal(p.name, f"CMS_SMP23001_Interference_{options.era}", 1.0798)
        
        # scale factors / resolution
        card.add_shape_nuisance(p.name, f"CMS_res_e_{year}"  , p.get("ElectronEn"), symmetrise=False)
        card.add_shape_nuisance(p.name, f"CMS_scale_m"  , p.get("MuonRoc")   , symmetrise=False)
        
        card.add_shape_nuisance(p.name, f"CMS_SMP23001_lept_sf_{options.era}", p.get("LeptonSF")  , symmetrise=False)
        card.add_shape_nuisance(p.name, f"CMS_SMP23001_trig_sf_{options.era}", p.get("triggerSF") , symmetrise=False)

        # JES/JES and UEPS 
        # card.add_shape_nuisance(p.name, f"CMS_scale_j_{options.era}", p.get("JES"), symmetrise=False) 

        card.add_shape_nuisance(p.name, f"CMS_scale_j_Absolute_{year}"      , p.get(f"JES_Absolute{year}")      , symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_scale_j_BBEC1_{year}"         , p.get(f"JES_BBEC1{year}")         , symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_scale_j_EC2_{year}"           , p.get(f"JES_EC2{year}")           , symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_scale_j_HF_{year}"            , p.get(f"JES_HF{year}")            , symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_scale_j_RelativeSample_{year}", p.get(f"JES_RelativeSample{year}"), symmetrise=False) 

        card.add_shape_nuisance(p.name, f"CMS_scale_j_Absolute"   , p.get("JES_Absolute")   , symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_scale_j_BBEC1"      , p.get("JES_BBEC1")      , symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_scale_j_EC2"        , p.get("JES_EC2")        , symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_scale_j_HF"         , p.get("JES_HF")         , symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_scale_j_RelativeBal", p.get("JES_RelativeBal"), symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_scale_j_FlavorQCD"  , p.get("JES_FlavorQCD")  , symmetrise=False) 
        card.add_shape_nuisance(p.name, f"CMS_res_j_{era_s}", p.get("JER"), symmetrise=False)
        card.add_shape_nuisance(p.name, f"CMS_scale_met_unclustered_energy_{era_s}", p.get("UES"), symmetrise=False)
        
        # no correlated over era's
        card.add_shape_nuisance(p.name, f"ps_fsr", p.get("UEPS_FSR"), symmetrise=False)
        card.add_shape_nuisance(p.name, f"ps_isr", p.get("UEPS_ISR"), symmetrise=False)
        
        # b-tagging uncertainties
        # btag_sf_bc_2016APV, btag_sf_light_2016APV
        try:
            card.add_shape_nuisance(p.name, f"CMS_btag_fixedWP_incl_light_uncorrelated_{era_s}" , p.get(f"btag_sf_light_{options.era}"), symmetrise=False)
            card.add_shape_nuisance(p.name, f"CMS_btag_fixedWP_comb_bc_uncorrelated_{era_s}"  , p.get(f"btag_sf_bc_{options.era}")   , symmetrise=False)
        except:
            pass
        
        # # b-tagging uncertainties correlated over years
        card.add_shape_nuisance(p.name, "CMS_btag_fixedWP_comb_bc_correlated"  , p.get("btag_sf_bc_correlated")   , symmetrise=False)
        card.add_shape_nuisance(p.name, "CMS_btag_fixedWP_incl_light_correlated" , p.get("btag_sf_light_correlated"), symmetrise=False)
        card.add_shape_nuisance(p.name, f"CMS_l1_ecal_prefiring_{era_s}" , p.get("prefiring_weight"), symmetrise=False)
        # # other uncertainties
        card.add_shape_nuisance(p.name, f"CMS_pileup_{year}", p.get("pileup_weight"), symmetrise=False)

        #QCD scale, PDF and other theory uncertainty
        if 'gg' not in p.name:
            qcd_shapes = []
            missing_qcd = False
            for key in ["QCDScale0w", "QCDScale1w", "QCDScale2w"]:
                try:
                    variation = p.get(key)
                except Exception as err:
                    print(f"--> missing {key} systematic for {p.name}: {err}")
                    missing_qcd = True
                    break
                if not isinstance(variation, tuple):
                    print(f"--> malformed {key} systematic for {p.name}, skipping QCD scale")
                    missing_qcd = True
                    break
                up_hist, down_hist = variation
                if not getattr(up_hist, "axes", None):
                    print(f"--> empty {key} systematic for {p.name}, skipping QCD scale")
                    missing_qcd = True
                    break
                qcd_shapes.append(variation)
            if not missing_qcd and len(qcd_shapes) == 3:
                if 'NLO' in p.name:
                    card.add_qcd_scales(
                        p.name, f"QCDscale_{p.name}",
                        qcd_shapes,normalize_to_nominal=True
                    )
                else:
                    card.add_qcd_scales(
                        p.name, f"QCDscale_{p.name}",
                        qcd_shapes#,normalize_to_nominal=True
                    )

        
        # PDF uncertaintites / not working for the moment
    
        if 'NLO' in p.name: 
            card.add_shape_nuisance(p.name, f"CMS_SMP23001_pdf_{p.name}"   , p.get("PDF_weight"), symmetrise=False,normalize_to_nominal=True)
        else:
            card.add_shape_nuisance(p.name, f"CMS_SMP23001_pdf_{p.name}"   , p.get("PDF_weight"), symmetrise=False)
        card.add_shape_nuisance(p.name, f"CMS_SMP23001_alphaS_{p.name}", p.get("aS_weight" ), symmetrise=False)        
        
        # Electroweak Corrections uncertainties
        if 'WZ' in p.name:
            card.add_shape_nuisance(p.name, "CMS_SMP23001_ewk_corr_WZ", p.get("kEW"), symmetrise=False)
        if ('ZZ' in p.name) and ('EWK' not in p.name):
            card.add_shape_nuisance(p.name, "CMS_SMP23001_ewk_corr_ZZ", p.get("kEW"), symmetrise=False)
          
        # define rates
        if p.name  in ["WW","Top"]:
           if "vbs-EM" in card_name:
               card.add_rate_param(f"CMS_SMP23001_NormWW_{options.era}", "vbs-EM*", p.name)
           elif "SR" in card_name:
               card.add_rate_param(f"CMS_SMP23001_NormWW_{options.era}", card_name+'*', p.name)
        
        # define rate 3L categoryel 
        elif p.name in ["WZ"]:
            if "vbs-3L" in card_name:
                card.add_rate_param(f"CMS_SMP23001_NormWZ_{options.era}", "vbs-3L*", p.name)
            elif "SR" in card_name:
                card.add_rate_param(f"CMS_SMP23001_NormWZ_{options.era}", card_name+'*', p.name)
        
        # define rate for DY category
        #elif p.name in ["DY"]:
        #    if "DY" in card_name:
        #        card.add_rate_param(f"NormDY_{options.era}", "vbs-DY*", p.name)
        #    elif "SR" in card_name:
        #        card.add_rate_param(f"NormDY_{options.era}", card_name+'*', p.name)
        
        card.add_auto_stat()

    # saving the datacard
    card.dump()

if __name__ == "__main__":
    main()
