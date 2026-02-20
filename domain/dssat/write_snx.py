from datetime import datetime, timedelta
from pathlib import Path
import re


CROP_CUL_FILES = {
    "ML": "MLCER047.CUL",
    "SG": "SGCER047.CUL",
    "RI": "RICER047.CUL",
    "PN": "PNGRO047.CUL",
}


def write_snx_file(scenario, x_filename, output_dir):
    """
    Generate a DSSAT SNX file with stable structure for DSSAT v4.7 executables.
    """
    d = scenario["dssat"]
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    crop = d.get("Crop", "ML")
    scenario_name = d.get("sce_name", "S001")
    stn_name = (d.get("stn_name", "BAMBY") or "BAMBY").upper()
    stn_name = re.sub(r"[^A-Z0-9]", "", stn_name)
    stn_code = (stn_name[:4] or "BAMB")
    cultivar_input = d.get("Cultivar", "IB0044")
    planting_density = int(d.get("plt_density", 5))
    planting_date = d.get("PltDate", "2026-06-15")

    soil_code = (
        scenario.get("location", {}).get("soil_code")
        or d.get("soil")
        or "IB00000010"
    )
    soil_code = str(soil_code)[:10]
    irrigation_enabled = bool(scenario.get("irrigation", {}).get("enabled"))
    irrigation_method = (scenario.get("irrigation", {}).get("method") or "AUTO").upper()
    fertilization_enabled = bool(scenario.get("fertilization", {}).get("enabled"))
    irrigation_schedule = scenario.get("irrigation", {}).get("schedule") or []
    auto_ir_amt = 10
    if irrigation_enabled and irrigation_schedule:
        try:
            auto_ir_amt = int(round(float(irrigation_schedule[0].get("mm", 10) or 10)))
        except Exception:
            auto_ir_amt = 10
    is_forecast = bool(scenario.get("dssat", {}).get("forecast_mode")) or str(
        scenario.get("dssat", {}).get("sce_name", "")
    ).startswith("F")
    def _valid_manual_event(ev):
        try:
            return (float(ev.get("mm", 0) or 0) > 0) and (int(ev.get("doy", -1)) >= 0)
        except Exception:
            return False

    has_manual_irrig_events = any(_valid_manual_event(ev) for ev in irrigation_schedule)
    # Use reported-date irrigation whenever manual schedule is defined
    # (forecast and historical), otherwise fallback to automatic if enabled.
    if irrigation_enabled and irrigation_method == "MANUAL" and has_manual_irrig_events:
        ma_irrig = "D"
        mi_factor = 1
    else:
        ma_irrig = "A" if irrigation_enabled else "N"
        mi_factor = 0
    if is_forecast and fertilization_enabled:
        ma_ferti = "D"
        mf_factor = 1
    else:
        ma_ferti = "D" if fertilization_enabled else "N"
        mf_factor = 1 if fertilization_enabled else 0

    cultivar_code, cultivar_name = resolve_cultivar(crop, cultivar_input, "/app/dssat")

    cycle_days = int(d.get("cycle_days", 210) or 210)
    pdate, icdat, hdate = dssat_dates(planting_date, cycle_days=cycle_days)

    snx_name = f"CL{crop}{scenario_name[:4]}.SNX"
    snx_path = output_dir / snx_name

    # DSSAT Fortran parsers are safer with DOS line endings.
    with open(snx_path, "w", encoding="ascii", newline="\r\n") as f:
        f.write("*EXP.DETAILS: SIMAGRI\n\n")

        f.write("*GENERAL\n")
        f.write("@PEOPLE\nSIMAGRI\n")
        f.write("@ADDRESS\nSenegal\n")
        f.write("@SITE\nSenegal\n")
        f.write("@ PAREA  PRNO  PLEN  PLDR  PLSP  PLAY HAREA  HRNO  HLEN  HARM.........\n")
        f.write("    -99   -99   -99   -99   -99   -99   -99   -99   -99   -99\n\n")

        f.write("*TREATMENTS                        -------------FACTOR LEVELS------------\n")
        f.write("@N R O C TNAME.................... CU FL SA IC MP MI MF MR MC MT ME MH SM\n")
        f.write(
            f" 1 1 0 0 SIMAGRI                    1  1  0  1  1  {mi_factor:>1}  {mf_factor:>1}  0  0  0  0  0  1\n\n"
        )

        f.write("*CULTIVARS\n")
        f.write("@C CR INGENO CNAME\n")
        f.write(f" 1 {crop:<2} {cultivar_code:<6} {cultivar_name}\n\n")

        f.write("*FIELDS\n")
        id_field = f"{stn_code}0001"
        f.write("@L ID_FIELD WSTA....  FLSA  FLOB  FLDT  FLDD  FLDS  FLST SLTX  SLDP  ID_SOIL    FLNAME\n")
        f.write(f" 1 {id_field:<8} {stn_code:<4}      -99   -99 DR000   -99   -99     0   -99    50  {soil_code:<10} -99\n")
        f.write("@L ...........XCRD ...........YCRD .....ELEV .............AREA .SLEN .FLWR .SLAS FLHST FHDUR\n")
        f.write(" 1            -99             -99       -99               -99   -99   -99   -99   -99   -99\n\n")

        f.write("*INITIAL CONDITIONS\n")
        f.write("@C   PCR ICDAT  ICRT  ICND  ICRN  ICRE  ICWD ICRES ICREN ICREP ICRIP ICRID ICNAME\n")
        f.write(f" 1    {crop:<2} {icdat:>5}   -99     0     1     1   -99     0     0     0   100    15 -99\n")
        f.write("@C  ICBL  SH2O  SNH4  SNO3\n")
        f.write(" 1    20  .147    .6   1.5\n")
        f.write(" 1    30  .197    .6   1.5\n\n")

        f.write("*PLANTING DETAILS\n")
        f.write("@P PDATE EDATE  PPOP  PPOE  PLME  PLDS  PLRS  PLRD  PLDP  PLWT  PAGE  PENV  PLPH  SPRL                        PLNAME\n")
        # Keep strict fixed-width numeric fields to satisfy IPPLNT parser.
        e_date = -99
        f.write(
            f" 1 {pdate:>5} {e_date:>5} {planting_density:>5} {planting_density:>5}     S     R    60     0     5   -99   -99   -99   -99   -99                        FIELD\n\n"
        )

        # Manual irrigation events for any scenario when requested.
        if irrigation_enabled and irrigation_method == "MANUAL" and has_manual_irrig_events:
            f.write("*IRRIGATION AND WATER MANAGEMENT\n")
            f.write("@I  EFIR  IDEP  ITHR  IEPT  IOFF  IAME  IAMT IRNAME\n")
            f.write(" 1     1    30    50   100 GS000 IR001    10 -99\n")
            # Match DSSAT template spacing for parser robustness.
            f.write("@I IDATE  IROP IRVAL\n")
            row = 0
            for ev in (scenario.get("irrigation", {}).get("schedule") or []):
                idate = int(ev.get("doy", -99))
                amt = float(ev.get("mm", 0) or 0)
                if idate < 0 or amt <= 0:
                    continue
                # Reported irrigation uses DAP (days after planting).
                amt_str = repr(amt)
                # Keep spacing consistent with historical writer.
                row += 1
                # DSSAT expects the treatment number in column 1 (always "1" here).
                f.write(f" 1   {idate:>3} IR001 {amt_str:>5}\n")
            f.write("\n")

        f.write("*FERTILIZERS (INORGANIC)\n")
        f.write("@F FDATE  FMCD  FACD  FDEP  FAMN  FAMP  FAMK  FAMC  FAMO  FOCD FERNAME\n")
        write_fertilizers(f, scenario)
        f.write("\n")

        f.write("*SIMULATION CONTROLS\n")
        f.write("@N GENERAL     NYERS NREPS START SDATE RSEED SNAME.................... SMODEL\n")
        f.write(f" 1 GE              1     1     S {icdat:>5}  2150 DEFAULT SIMULATION CONTR  {crop}CER\n")
        f.write("@N OPTIONS     WATER NITRO SYMBI PHOSP POTAS DISES  CHEM  TILL   CO2\n")
        f.write(" 1 OP              Y     Y     Y     N     N     N     N     N     D\n")
        f.write("@N METHODS     WTHER INCON LIGHT EVAPO INFIL PHOTO HYDRO NSWIT MESOM MESEV MESOL\n")
        f.write(" 1 ME              M     M     E     R     S     C     R     1     G     S     2\n")
        f.write("@N MANAGEMENT  PLANT IRRIG FERTI RESID HARVS\n")
        f.write(f" 1 MA              R     {ma_irrig}     {ma_ferti}     N     M\n")
        f.write("@N OUTPUTS     FNAME OVVEW SUMRY FROPT GROUT CAOUT WAOUT NIOUT MIOUT DIOUT VBOSE CHOUT OPOUT FMOPT\n")
        f.write(" 1 OU              N     Y     Y     1     N     N     N     N     N     N     N     N     Y     A\n\n")

        f.write("@  AUTOMATIC MANAGEMENT\n")
        f.write("@N PLANTING    PFRST PLAST PH2OL PH2OU PH2OD PSTMX PSTMN\n")
        f.write(f" 1 PL          {pdate:>5} {pdate:>5}    40   100    30    40    10\n")
        f.write("@N IRRIGATION  IMDEP ITHRL ITHRU IROFF IMETH IRAMT IREFF\n")
        f.write(f" 1 IR             30    50   100 GS000 IR001 {auto_ir_amt:>5}     1\n")
        f.write("@N NITROGEN    NMDEP NMTHR NAMNT NCODE NAOFF\n")
        f.write(" 1 NI              5    50    25 FE005 GS000\n")
        f.write("@N RESIDUES    RIPCN RTIME RIDEP\n")
        f.write(" 1 RE            100     1    20\n")
        f.write("@N HARVEST     HFRST HLAST HPCNP HPCNR\n")
        f.write(f" 1 HA              0 {hdate:>5}   100     0\n")

    print(f"SNX file written: {snx_path}")
    return snx_path


def dssat_dates(planting_date, cycle_days=210):
    dt = parse_date(planting_date)
    doy = dt.timetuple().tm_yday
    pdate = f"{dt.year % 100:02d}{doy:03d}"

    ic_dt = dt - timedelta(days=1)
    icdat = f"{ic_dt.year % 100:02d}{ic_dt.timetuple().tm_yday:03d}"

    hv_dt = dt + timedelta(days=cycle_days)
    hdate = f"{hv_dt.year % 100:02d}{hv_dt.timetuple().tm_yday:03d}"
    return pdate, icdat, hdate


def parse_date(value):
    value = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def resolve_cultivar(crop, cultivar, dssat_path):
    cul_file = CROP_CUL_FILES.get(crop)
    if not cul_file:
        return str(cultivar)[:6], "SIMAGRI"

    cul_path = Path(dssat_path) / cul_file
    if not cul_path.exists():
        return str(cultivar)[:6], "SIMAGRI"

    target = str(cultivar).strip().upper()
    first = None

    with open(cul_path, "r", encoding="latin-1", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith(("!", "*", "@")):
                continue
            parts = re.split(r"\s+", line)
            code = parts[0].upper()
            if not re.match(r"^[A-Z0-9]{6}$", code):
                continue
            name = parts[1] if len(parts) > 1 else "SIMAGRI"
            if first is None:
                first = (code, name)
            if code == target:
                return code, name

    if first:
        return first
    return str(cultivar)[:6], "SIMAGRI"


def write_fertilizers(file_obj, scenario):
    applications = scenario.get("fertilization", {}).get("applications", [])
    row = 0
    is_forecast = bool(scenario.get("dssat", {}).get("forecast_mode")) or str(scenario.get("dssat", {}).get("sce_name", "")).startswith("F")
    for app in applications:
        doy = int(app.get("doy", -99))
        n_val = float(app.get("N", 0))
        p_val = float(app.get("P", 0))
        k_val = float(app.get("K", 0))
        if doy < 0:
            continue
        fmcd = "FE005"
        # Use the same valid codes/depth as DSSAT templates.
        facd = "AP002"
        fdep = 4
        # DSSAT expects the treatment number in column 1 (always "1" here).
        row += 1
        file_obj.write(
            f" 1   {doy:>3} {fmcd:>5} {facd:>5} {fdep:>5} "
            f"{n_val:>5.0f} {p_val:>5.0f} {k_val:>5.0f}   -99   -99   -99 -99\n"
        )
