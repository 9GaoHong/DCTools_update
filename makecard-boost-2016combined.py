import argparse
from copy import deepcopy
from typing import Any, Dict, List, Tuple

import dctools


def sum_histograms(histograms: List) -> Any:
    valid = [h for h in histograms if getattr(h, "axes", None)]
    if not valid:
        return None
    total = deepcopy(valid[0])
    for hist in valid[1:]:
        total = total + hist
    return total


def combine_shape_variation(
    groups_by_era: Dict[str, Any],
    key: str,
    nominals_by_era: Dict[str, Any],
    target_eras: List[str] = None
) -> Tuple[Any, Any]:
    up_total = None
    down_total = None
    has_effect = False

    for era, group in groups_by_era.items():
        nominal = nominals_by_era.get(era)
        if nominal is None:
            continue
        try:
            variation = group.get(key)
        except Exception:
            variation = None

        up_hist, down_hist = None, None
        if isinstance(variation, tuple):
            up_hist, down_hist = variation
            if not getattr(up_hist, "axes", None):
                up_hist, down_hist = None, None

        use_variation = False
        if target_eras is None:
            use_variation = up_hist is not None
        else:
            use_variation = (era in target_eras) and (up_hist is not None)

        if use_variation:
            has_effect = True
            up_part = up_hist
            down_part = down_hist
        else:
            up_part = nominal
            down_part = nominal

        if up_total is None:
            up_total = up_part
            down_total = down_part
        else:
            up_total = up_total + up_part
            down_total = down_total + down_part

    if not has_effect or up_total is None or down_total is None:
        return None
    return up_total, down_total


def load_datasets(config_path: str, era: str, options) -> Tuple[Any, Dict[str, Any], str]:
    config = dctools.read_config(config_path)
    datasets: Dict[str, Any] = {}
    signal = ""

    for name in config.groups:
        histograms = dict(
            filter(
                lambda _n: _n[0] in config.groups[name].processes,
                config.boosthist.items()
            )
        )

        datagroup = dctools.datagroup(
            histograms=histograms,
            ptype=config.groups[name].type,
            observable=options.variable,
            name=name,
            xsections=config.xsections,
            channel=options.channel,
            luminosity=config.luminosity.value,
            rebin=options.rebin,
            era=era
        )

        datasets[datagroup.name] = datagroup
        if datagroup.ptype == "signal":
            signal = datagroup.name

    return config, datasets, signal


def main():
    parser = argparse.ArgumentParser(
        description='Combine 2016 and 2016APV into a single datacard'
    )
    parser.add_argument(
        "-i", "--input2016", type=str,
        default="./config/input_UL_2016-fes.yaml",
        help="configuration file for 2016"
    )
    parser.add_argument(
        "--input2016apv", type=str,
        default="./config/input_UL_2016APV-fes.yaml",
        help="configuration file for 2016APV"
    )
    parser.add_argument("-v", "--variable", type=str, default="gnn_score")
    parser.add_argument(
        "-c", "--channel", nargs='+', type=str, required=True,
        help="analysis channel"
    )
    parser.add_argument("-s", "--signal", nargs='+', type=str)
    parser.add_argument('-n', "--name", type=str, default='')
    parser.add_argument('--rebin', type=int, default=1, help='rebin')
    parser.add_argument(
        "--era", type=str, default="2016all",
        help="label for the combined era used in output names"
    )
    parser.add_argument("--bins",
                        type=lambda s: [float(item) for item in s.split(',')],
                        help='comma separated list. ex: --bins="-1.2,0,1.2"')
    parser.add_argument('--blind', action='store_true')
    parser.add_argument('--checksyst', action='store_true')
    parser.add_argument("-d", '--dd', type=bool, default=False)

    options = parser.parse_args()

    if len(options.channel) == 1:
        options.channel = options.channel[0]
    else:
        raise ValueError("Only a single channel is supported when combining eras.")

    if options.name == '':
        options.name = options.channel

    eras = {
        "2016": options.input2016,
        "2016APV": options.input2016apv,
    }

    configs: Dict[str, Any] = {}
    datasets_by_era: Dict[str, Dict[str, Any]] = {}
    signal_name = ""

    for era_label, cfg_path in eras.items():
        config, datasets, signal = load_datasets(cfg_path, era_label, options)
        configs[era_label] = config
        datasets_by_era[era_label] = datasets
        if signal:
            signal_name = signal

    print(f'making combined card for {options.channel} : {options.variable} : {options.era}')

    data_hist = sum_histograms([
        datasets_by_era[era]["data"].get("nominal")
        for era in eras
        if "data" in datasets_by_era[era]
    ])

    if data_hist is None:
        raise RuntimeError("Could not build data observation for the combined eras.")

    card_name = options.channel + options.era

    card = dctools.datacard(
        name=signal_name if len(options.name) == 0 else options.name,
        channel=card_name
    )
    card.shapes_headers()
    card.add_observation(data_hist)

    process_names = set()
    for datasets in datasets_by_era.values():
        process_names.update(datasets.keys())

    process_names.discard("data")
    year_common = "2016"
    era_suffix = {"2016": "2016", "2016APV": "2016preVFP"}
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

    for pname in sorted(process_names):
        per_era_groups = {
            era: datasets[pname]
            for era, datasets in datasets_by_era.items()
            if pname in datasets
        }

        if not per_era_groups:
            continue

        valid_groups = {
            era: group
            for era, group in per_era_groups.items()
            if len(group.to_boost().shape) > 0
        }

        if not valid_groups:
            print(f"--> histogram for the process {pname} is empty !")
            continue

        nominals: Dict[str, Any] = {}
        for era, group in valid_groups.items():
            try:
                nominals[era] = group.get("nominal")
            except ValueError:
                continue

        if not nominals:
            print(f"--> histogram for the process {pname} is empty !")
            continue

        combined_nominal = sum_histograms(list(nominals.values()))
        if combined_nominal is None:
            print(f"--> histogram for the process {pname} is empty !")
            continue

        if combined_nominal.sum().value == 0:
            print(f"--> histogram for the process {pname} is empty !")
            continue

        template_group = next(iter(valid_groups.values()))
        if template_group.ptype == "data":
            continue

        print(pname)
        if not card.add_nominal(pname, combined_nominal, template_group.ptype):
            continue

        if "DY" in pname and options.dd:
            print("Adding data-driven DY uncertainties")
            shape = combine_shape_variation(
                valid_groups,
                f"dataDrivenDYRatio_{year_common}",
                nominals
            )
            if shape:
                # dd_shape = _scale_dd_uncertainty(shape, year)
                card.add_shape_nuisance(p.name, f"CMS_SMP23001_DY_dd_uncert_{year}", dd_shape, symmetrise=False)
                #card.add_shape_nuisance(
                #    pname,
                #    f"CMS_SMP23001_DY_dd_uncert_{year_common}",
                #    shape,
                #    symmetrise=False
                #)
            card.add_auto_stat()
            continue

        if 'WW' not in pname and 'WZ' not in pname and 'DY' not in pname and 'Top' not in pname:
            config = configs["2016"]
          
            card.add_log_normal_lumi(pname, f"lumi_2016", config.luminosity.uncer)
            card.add_log_normal_lumi(pname, f"lumi_13TeV_1617", config.luminosity.uncer_correlated_1617)
            card.add_log_normal_lumi(pname, f"lumi_13TeV_correlated", config.luminosity.uncer_correlated_161718)

        for era in valid_groups:
            card.add_log_normal(pname, f"CMS_SMP23001_Interference_{era}", 1.0798)

        shape = combine_shape_variation(valid_groups, "ElectronEn", nominals)
        if shape:
            card.add_shape_nuisance(pname, f"CMS_res_e_{year_common}", shape, symmetrise=False)

        shape = combine_shape_variation(valid_groups, "MuonRoc", nominals)
        if shape:
            card.add_shape_nuisance(pname, "CMS_scale_m", shape, symmetrise=False)

        for era in valid_groups:
            shape = combine_shape_variation(
                valid_groups,
                "LeptonSF",
                nominals,
                target_eras=[era]
            )
            if shape:
                card.add_shape_nuisance(
                    pname,
                    f"CMS_SMP23001_lept_sf_{era}",
                    shape,
                    symmetrise=False
                )

            shape = combine_shape_variation(
                valid_groups,
                "triggerSF",
                nominals,
                target_eras=[era]
            )
            if shape:
                card.add_shape_nuisance(
                    pname,
                    f"CMS_SMP23001_trig_sf_{era}",
                    shape,
                    symmetrise=False
                )

        for jes_name in [
            ("CMS_scale_j_Absolute_{year}", f"JES_Absolute{year_common}"),
            ("CMS_scale_j_BBEC1_{year}", f"JES_BBEC1{year_common}"),
            ("CMS_scale_j_EC2_{year}", f"JES_EC2{year_common}"),
            ("CMS_scale_j_HF_{year}", f"JES_HF{year_common}"),
            ("CMS_scale_j_RelativeSample_{year}", f"JES_RelativeSample{year_common}"),
            ("CMS_scale_j_Absolute", "JES_Absolute"),
            ("CMS_scale_j_BBEC1", "JES_BBEC1"),
            ("CMS_scale_j_EC2", "JES_EC2"),
            ("CMS_scale_j_HF", "JES_HF"),
            ("CMS_scale_j_RelativeBal", "JES_RelativeBal"),
            ("CMS_scale_j_FlavorQCD", "JES_FlavorQCD"),
        ]:
            card_label = jes_name[0].replace("{year}", year_common)
            shape = combine_shape_variation(valid_groups, jes_name[1], nominals)
            if shape:
                card.add_shape_nuisance(pname, card_label, shape, symmetrise=False)

        for era, suffix in era_suffix.items():
            if era not in valid_groups:
                continue
            shape = combine_shape_variation(
                valid_groups,
                "JER",
                nominals,
                target_eras=[era]
            )
            if shape:
                card.add_shape_nuisance(
                    pname,
                    f"CMS_res_j_{suffix}",
                    shape,
                    symmetrise=False
                )

            shape = combine_shape_variation(
                valid_groups,
                "UES",
                nominals,
                target_eras=[era]
            )
            if shape:
                card.add_shape_nuisance(
                    pname,
                    f"CMS_scale_met_unclustered_energy_{suffix}",
                    shape,
                    symmetrise=False
                )

        for key, label in [("UEPS_FSR", "ps_fsr"), ("UEPS_ISR", "ps_isr")]:
            shape = combine_shape_variation(valid_groups, key, nominals)
            if shape:
                card.add_shape_nuisance(pname, label, shape, symmetrise=False)

        for era, suffix in era_suffix.items():
            if era not in valid_groups:
                continue
            for key, label in [
                (f"btag_sf_light_{era}", f"CMS_btag_fixedWP_incl_light_uncorrelated_{suffix}"),
                (f"btag_sf_bc_{era}", f"CMS_btag_fixedWP_comb_bc_uncorrelated_{suffix}"),
                ("prefiring_weight", f"CMS_l1_ecal_prefiring_{suffix}")
            ]:
                shape = combine_shape_variation(
                    valid_groups,
                    key,
                    nominals,
                    target_eras=[era]
                )
                if shape:
                    card.add_shape_nuisance(pname, label, shape, symmetrise=False)

        for key, label in [
            ("btag_sf_bc_correlated", "CMS_btag_fixedWP_comb_bc_correlated"),
            ("btag_sf_light_correlated", "CMS_btag_fixedWP_incl_light_correlated"),
            ("pileup_weight", f"CMS_pileup_{year_common}")
        ]:
            shape = combine_shape_variation(valid_groups, key, nominals)
            if shape:
                card.add_shape_nuisance(pname, label, shape, symmetrise=False)

        if 'gg' not in pname:
            qcd_shapes = []
            for key in ["QCDScale0w", "QCDScale1w", "QCDScale2w"]:
                shape = combine_shape_variation(valid_groups, key, nominals)
                if shape:
                    qcd_shapes.append(shape)
            if len(qcd_shapes) == 3:
                if 'NLO' in pname:
                    card.add_qcd_scales(
                        pname, f"QCDscale_{pname}",
                        qcd_shapes,normalize_to_nominal=True
                    )
                else:
                    card.add_qcd_scales(
                        pname,
                        f"QCDscale_{pname}",
                        qcd_shapes
                    )

        for key, label in [
            ("PDF_weight", f"CMS_SMP23001_pdf_{pname}"),
            ("aS_weight", f"CMS_SMP23001_alphaS_{pname}")
        ]:
            shape = combine_shape_variation(valid_groups, key, nominals)

            if shape:
                if 'NLO' in pname and "PDF" in key:
                    card.add_shape_nuisance(
                        pname, label,
                        shape,normalize_to_nominal=True
                    )
                else:
                    card.add_shape_nuisance(pname, label, shape, symmetrise=False)

        if 'WZ' in pname:
            shape = combine_shape_variation(valid_groups, "kEW", nominals)
            if shape:
                card.add_shape_nuisance(pname, "CMS_SMP23001_ewk_corr_WZ", shape, symmetrise=False)
        if 'ZZ' in pname and 'EWK' not in pname:
            shape = combine_shape_variation(valid_groups, "kEW", nominals)
            if shape:
                card.add_shape_nuisance(pname, "CMS_SMP23001_ewk_corr_ZZ", shape, symmetrise=False)

        if pname in ["WW", "Top"]:
            if "vbs-EM" in card_name:
                card.add_rate_param(f"CMS_SMP23001_NormWW_{options.era}", "vbs-EM*", pname)
            elif "SR" in card_name:
                card.add_rate_param(f"CMS_SMP23001_NormWW_{options.era}", card_name + '*', pname)
        elif pname in ["WZ"]:
            if "vbs-3L" in card_name:
                card.add_rate_param(f"CMS_SMP23001_NormWZ_{options.era}", "vbs-3L*", pname)
            elif "SR" in card_name:
                card.add_rate_param(f"CMS_SMP23001_NormWZ_{options.era}", card_name + '*', pname)

        card.add_auto_stat()

    card.dump()


if __name__ == "__main__":
    main()
