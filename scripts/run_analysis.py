"""CLI entry point for the LGD Development Factor Model.

Usage:
    python scripts/run_analysis.py data/Munic_dashboard_LPU_1.xlsx
    python scripts/run_analysis.py data/Munic_dashboard_LPU_1.xlsx --windows 12,18,24,60
"""

import argparse
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from lgd_model.config import ModelConfig
from lgd_model.scenario import run_multi_scenario
from lgd_model.export import export_multi_scenario_excel, export_results_to_excel
from lgd_model.dashboard import generate_dashboard
from lgd_model.data_loader import load_recovery_triangle
from lgd_model.vintage import run_vintage_analysis
from lgd_model.backtest import run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LGD Development Factor Model — CLI",
    )
    parser.add_argument("filepath", help="Path to the input Excel workbook")
    parser.add_argument(
        "--windows",
        default="12,18,24,30,36,42,48,54,60",
        help="Comma-separated window sizes (default: 12,18,24,30,36,42,48,54,60)",
    )
    parser.add_argument("--discount-rate", type=float, default=0.15)
    parser.add_argument("--ci-percentile", type=float, default=0.75,
                        help="CI percentile (0.50-0.99, default 0.75). z derived via norm.ppf.")
    parser.add_argument("--lgd-cap", type=float, default=None)
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: same as input file)")

    args = parser.parse_args()

    window_sizes = [int(w.strip()) for w in args.windows.split(",")]
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(args.filepath)) or '.'

    base_config = ModelConfig(
        discount_rate=args.discount_rate,
        window_size=60,
        max_tid=60,
        lgd_cap=args.lgd_cap,
        ci_percentile=args.ci_percentile,
    )

    # Run multi-scenario analysis
    scenarios = run_multi_scenario(
        filepath=args.filepath,
        window_sizes=window_sizes,
        base_config=base_config,
        verbose=True,
    )

    if not scenarios:
        print("ERROR: No scenarios produced valid results.")
        sys.exit(1)

    # Export multi-scenario Excel
    xlsx_path = os.path.join(output_dir, 'LGD_Multi_Scenario_Output.xlsx')
    export_multi_scenario_excel(scenarios, xlsx_path)

    # Generate dashboard
    dash_path = os.path.join(output_dir, 'LGD_Dashboard.html')
    generate_dashboard(scenarios, output_path=dash_path)

    # Single best-window detailed output
    best = scenarios[0]
    best_config = ModelConfig(
        discount_rate=args.discount_rate,
        window_size=best.window_size,
        max_tid=min(best.window_size, 60),
        lgd_cap=args.lgd_cap,
        ci_percentile=args.ci_percentile,
    )
    single_xlsx = os.path.join(output_dir, 'LGD_Model_Output.xlsx')
    master_df = load_recovery_triangle(args.filepath)
    vintage_results = run_vintage_analysis(master_df, best_config)
    bt = run_backtest(vintage_results, best_config)
    export_results_to_excel(vintage_results, bt, best_config, single_xlsx)

    print(f"\nDone. Outputs saved to {output_dir}")


if __name__ == '__main__':
    main()
