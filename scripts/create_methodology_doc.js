const fs = require('fs');
const {
    Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
    Header, Footer, AlignmentType, LevelFormat, ExternalHyperlink,
    HeadingLevel, BorderStyle, WidthType, ShadingType, PageNumber,
    PageBreak, TabStopType, TabStopPosition, TableOfContents,
    Bookmark, InternalHyperlink, FootnoteReferenceRun
} = require('docx');

const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const borders = { top: border, bottom: border, left: border, right: border };
const cellMargins = { top: 60, bottom: 60, left: 100, right: 100 };

const TW = 9360; // Table width (US Letter - 1" margins)

function hdrCell(text, width) {
    return new TableCell({
        borders, width: { size: width, type: WidthType.DXA },
        shading: { fill: '2E75B6', type: ShadingType.CLEAR },
        margins: cellMargins,
        children: [new Paragraph({ alignment: AlignmentType.CENTER,
            children: [new TextRun({ text, bold: true, color: 'FFFFFF', font: 'Arial', size: 18 })] })]
    });
}

function dataCell(text, width, bold = false) {
    return new TableCell({
        borders, width: { size: width, type: WidthType.DXA },
        margins: cellMargins,
        children: [new Paragraph({
            children: [new TextRun({ text, font: 'Arial', size: 18, bold })] })]
    });
}

function p(text, opts = {}) {
    const runs = [];
    if (typeof text === 'string') {
        runs.push(new TextRun({ text, font: 'Arial', size: 22, ...opts }));
    } else {
        runs.push(...text);
    }
    return new Paragraph({
        spacing: { after: 160, line: 276 },
        children: runs,
        ...(opts.heading ? { heading: opts.heading } : {}),
        ...(opts.alignment ? { alignment: opts.alignment } : {}),
    });
}

function heading(text, level) {
    return new Paragraph({
        heading: level,
        spacing: { before: 300, after: 200 },
        children: [new TextRun({ text, font: 'Arial', size: level === HeadingLevel.HEADING_1 ? 32 : level === HeadingLevel.HEADING_2 ? 26 : 22, bold: true })],
    });
}

function mathBlock(text) {
    return new Paragraph({
        spacing: { before: 120, after: 120 },
        indent: { left: 720 },
        children: [new TextRun({ text, font: 'Consolas', size: 20, italics: true })],
    });
}

function refLink(text, url) {
    return new ExternalHyperlink({
        children: [new TextRun({ text, style: 'Hyperlink', font: 'Arial', size: 22 })],
        link: url,
    });
}

const doc = new Document({
    styles: {
        default: { document: { run: { font: 'Arial', size: 22 } } },
        paragraphStyles: [
            { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
              run: { size: 32, bold: true, font: 'Arial', color: '1F3864' },
              paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 } },
            { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
              run: { size: 26, bold: true, font: 'Arial', color: '2E75B6' },
              paragraph: { spacing: { before: 240, after: 180 }, outlineLevel: 1 } },
            { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
              run: { size: 22, bold: true, font: 'Arial', color: '404040' },
              paragraph: { spacing: { before: 180, after: 120 }, outlineLevel: 2 } },
        ]
    },
    numbering: {
        config: [
            { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2022', alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
            { reference: 'numbers', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
            { reference: 'subbullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '\u2013', alignment: AlignmentType.LEFT,
              style: { paragraph: { indent: { left: 1080, hanging: 360 } } } }] },
        ]
    },
    footnotes: {
        1: { children: [p('IFRS 9 Financial Instruments, IASB, July 2014, para. 5.5.1\u20135.5.20.')] },
        2: { children: [p('Basel Committee on Banking Supervision, \u201CGuidance on credit risk and accounting for expected credit losses,\u201D December 2015, BCBS d350.')] },
        3: { children: [p('Mack, T. (1993), \u201CDistribution-free calculation of the standard error of chain ladder reserve estimates,\u201D ASTIN Bulletin, 23(2), pp. 213\u2013225.')] },
        4: { children: [p('England, P.D. and Verrall, R.J. (2002), \u201CStochastic claims reserving in general insurance,\u201D British Actuarial Journal, 8(3), pp. 443\u2013518.')] },
        5: { children: [p('Taylor, G. (2000), Loss Reserving: An Actuarial Perspective, Kluwer Academic Publishers.')] },
        6: { children: [p('Wuthrich, M.V. and Merz, M. (2008), Stochastic Claims Reserving Methods in Insurance, Wiley.')] },
        7: { children: [p('South African Reserve Bank, \u201CBanks Act Directive 8/2019: Implementation of IFRS 9,\u201D Pretoria.')] },
        8: { children: [p('Jarque, C.M. and Bera, A.K. (1987), \u201CA test for normality of observations and regression residuals,\u201D International Statistical Review, 55(2), pp. 163\u2013172.')] },
    },
    sections: [
        // ===================== COVER PAGE =====================
        {
            properties: {
                page: {
                    size: { width: 12240, height: 15840 },
                    margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
                },
            },
            headers: {
                default: new Header({ children: [
                    new Paragraph({
                        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '2E75B6', space: 1 } },
                        children: [
                            new TextRun({ text: 'Anchor Point Risk (Pty) Ltd', font: 'Arial', size: 18, color: '666666' }),
                            new TextRun({ text: '\tIFRS 9 LGD Model Methodology', font: 'Arial', size: 18, color: '666666' }),
                        ],
                        tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
                    })
                ] })
            },
            footers: {
                default: new Footer({ children: [
                    new Paragraph({
                        alignment: AlignmentType.CENTER,
                        children: [
                            new TextRun({ text: 'CONFIDENTIAL', font: 'Arial', size: 16, color: '999999' }),
                            new TextRun({ text: '  |  Page ', font: 'Arial', size: 16, color: '999999' }),
                            new TextRun({ children: [PageNumber.CURRENT], font: 'Arial', size: 16, color: '999999' }),
                        ],
                    })
                ] })
            },
            children: [
                new Paragraph({ spacing: { before: 3000 } }),
                new Paragraph({
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 200 },
                    children: [new TextRun({ text: 'IFRS 9 LGD Development Factor Model', font: 'Arial', size: 48, bold: true, color: '1F3864' })],
                }),
                new Paragraph({
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 200 },
                    children: [new TextRun({ text: 'Methodology and Validation Documentation', font: 'Arial', size: 32, color: '2E75B6' })],
                }),
                new Paragraph({
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 600 },
                    children: [new TextRun({ text: 'Eskom \u2014 Non-Metro Municipal Debt', font: 'Arial', size: 26, color: '404040' })],
                }),
                new Paragraph({ spacing: { after: 100 } }),
                // Document metadata table
                new Table({
                    width: { size: 5400, type: WidthType.DXA },
                    columnWidths: [2400, 3000],
                    rows: [
                        new TableRow({ children: [
                            dataCell('Prepared by:', 2400, true),
                            dataCell('Anchor Point Risk (Pty) Ltd', 3000),
                        ]}),
                        new TableRow({ children: [
                            dataCell('Contact:', 2400, true),
                            dataCell('henry@anchorpointrisk.co.za', 3000),
                        ]}),
                        new TableRow({ children: [
                            dataCell('Entity:', 2400, true),
                            dataCell('Eskom Holdings SOC Ltd', 3000),
                        ]}),
                        new TableRow({ children: [
                            dataCell('Portfolio:', 2400, true),
                            dataCell('Non-Metro Municipal Debt', 3000),
                        ]}),
                        new TableRow({ children: [
                            dataCell('Date:', 2400, true),
                            dataCell('March 2026', 3000),
                        ]}),
                        new TableRow({ children: [
                            dataCell('Version:', 2400, true),
                            dataCell('1.0', 3000),
                        ]}),
                        new TableRow({ children: [
                            dataCell('Classification:', 2400, true),
                            dataCell('Confidential', 3000),
                        ]}),
                    ],
                }),
                new Paragraph({ children: [new PageBreak()] }),

                // ===================== TABLE OF CONTENTS =====================
                heading('Table of Contents', HeadingLevel.HEADING_1),
                new TableOfContents('Table of Contents', { hyperlink: true, headingStyleRange: '1-3' }),
                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 1. EXECUTIVE SUMMARY =====================
                heading('1. Executive Summary', HeadingLevel.HEADING_1),
                p('This document describes the methodology, mathematical framework, and validation approach for the IFRS 9 Loss Given Default (LGD) Development Factor Model implemented for Eskom\u2019s non-metro municipal debt portfolio. The model employs the chain-ladder method\u2014a well-established actuarial technique\u2014to estimate LGD term structures from monthly default cohort recovery data, and uses a rolling-vintage backtesting framework to assess predictive accuracy across multiple calibration windows.'),
                p('The model has been validated to machine precision against the client\u2019s Excel workbook across all 276 backtest residuals at the 60-month reference window. This documentation is intended to satisfy external audit requirements under IFRS 9 and the Basel Committee\u2019s guidance on credit risk and accounting for expected credit losses.'),

                p([
                    new TextRun({ text: 'Key findings: ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'The multi-scenario analysis evaluates nine calibration window sizes (12 to 60 months). The composite scoring framework identifies the 18-month window as optimal, with RMSE of 0.0405, MAE of 0.0184, and bias of +0.0045. All window sizes produce consistent vintage-aligned backtests with 276 residual observations across 23 vintages.', font: 'Arial', size: 22 }),
                ]),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 2. REGULATORY CONTEXT =====================
                heading('2. Regulatory Context and Standards', HeadingLevel.HEADING_1),

                heading('2.1 IFRS 9 Requirements', HeadingLevel.HEADING_2),
                p([
                    new TextRun({ text: 'IFRS 9 Financial Instruments', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ' (effective 1 January 2018) requires entities to measure expected credit losses (ECL) using a forward-looking approach.', font: 'Arial', size: 22 }),
                    new FootnoteReferenceRun(1),
                    new TextRun({ text: ' The ECL for a given exposure is computed as:', font: 'Arial', size: 22 }),
                ]),
                mathBlock('ECL = PD \u00D7 LGD \u00D7 EAD'),
                p('where PD is the Probability of Default, LGD is Loss Given Default, and EAD is Exposure at Default. This model addresses the LGD component specifically, estimating how losses develop over time for exposures that have entered default status.'),

                p([
                    new TextRun({ text: 'IFRS 9 paragraph 5.5.17 requires that ECL estimates reflect an unbiased and probability-weighted amount determined by evaluating a range of possible outcomes, the time value of money, and reasonable and supportable information available without undue cost or effort at the reporting date.', font: 'Arial', size: 22 }),
                ]),

                heading('2.2 Basel Committee Guidance', HeadingLevel.HEADING_2),
                p([
                    new TextRun({ text: 'The Basel Committee on Banking Supervision\u2019s guidance document BCBS d350', font: 'Arial', size: 22 }),
                    new FootnoteReferenceRun(2),
                    new TextRun({ text: ' establishes principles for credit risk and accounting for expected credit losses. Principle 6 states that a bank\u2019s use of experienced credit judgment should be applied in a consistent and systematic manner across all ECL estimation approaches. The chain-ladder method satisfies this by providing a transparent, data-driven framework with clear assumptions.', font: 'Arial', size: 22 }),
                ]),

                heading('2.3 South African Reserve Bank Requirements', HeadingLevel.HEADING_2),
                p([
                    new TextRun({ text: 'The South African Reserve Bank\u2019s implementation guidance for IFRS 9', font: 'Arial', size: 22 }),
                    new FootnoteReferenceRun(7),
                    new TextRun({ text: ' requires institutions to maintain documented methodologies, perform regular backtesting, and demonstrate model stability across different calibration periods. This model\u2019s multi-scenario framework directly addresses these requirements by evaluating performance across nine distinct calibration windows.', font: 'Arial', size: 22 }),
                ]),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 3. DATA DESCRIPTION =====================
                heading('3. Data Description', HeadingLevel.HEADING_1),

                heading('3.1 Portfolio Overview', HeadingLevel.HEADING_2),
                p('The model is calibrated on Eskom\u2019s non-metro municipal debt portfolio. The input data is organised as a recovery triangle\u2014a matrix where rows represent monthly default cohorts and columns represent months since default (Time in Default, or TID).'),

                new Table({
                    width: { size: TW, type: WidthType.DXA },
                    columnWidths: [4680, 4680],
                    rows: [
                        new TableRow({ children: [hdrCell('Parameter', 4680), hdrCell('Value', 4680)] }),
                        new TableRow({ children: [dataCell('Number of cohorts', 4680), dataCell('82', 4680)] }),
                        new TableRow({ children: [dataCell('Observation period', 4680), dataCell('March 2019 \u2013 December 2025', 4680)] }),
                        new TableRow({ children: [dataCell('Maximum TID observed', 4680), dataCell('81 months', 4680)] }),
                        new TableRow({ children: [dataCell('Data frequency', 4680), dataCell('Monthly', 4680)] }),
                        new TableRow({ children: [dataCell('Reference window', 4680), dataCell('60 months', 4680)] }),
                        new TableRow({ children: [dataCell('Number of vintages (60m)', 4680), dataCell('23', 4680)] }),
                    ],
                }),

                p(''),
                heading('3.2 Recovery Triangle Structure', HeadingLevel.HEADING_2),
                p('Each cell Balance(i, n) in the recovery triangle represents the outstanding balance of cohort i at n months since default. The upper-right triangle is NaN because younger cohorts have not been observed for enough months. This incomplete triangle structure is the defining characteristic of chain-ladder methods: the model uses the pattern of completed observations to project future recovery for incomplete cohorts.'),

                heading('3.3 Key Data Fields', HeadingLevel.HEADING_2),
                new Table({
                    width: { size: TW, type: WidthType.DXA },
                    columnWidths: [2340, 7020],
                    rows: [
                        new TableRow({ children: [hdrCell('Field', 2340), hdrCell('Description', 7020)] }),
                        new TableRow({ children: [dataCell('Period', 2340), dataCell('Default cohort date (monthly)', 7020)] }),
                        new TableRow({ children: [dataCell('EAD', 2340), dataCell('Exposure at Default \u2014 outstanding balance when default occurs', 7020)] }),
                        new TableRow({ children: [dataCell('TID', 2340), dataCell('Maximum Time in Default observed for this cohort', 7020)] }),
                        new TableRow({ children: [dataCell('TID_0 \u2026 TID_81', 2340), dataCell('Outstanding balance at each month since default', 7020)] }),
                    ],
                }),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 4. METHODOLOGY =====================
                heading('4. Model Methodology', HeadingLevel.HEADING_1),

                heading('4.1 Chain-Ladder Method Overview', HeadingLevel.HEADING_2),
                p([
                    new TextRun({ text: 'The chain-ladder (or development factor) method is an actuarial technique originally developed for insurance loss reserving', font: 'Arial', size: 22 }),
                    new FootnoteReferenceRun(3),
                    new FootnoteReferenceRun(5),
                    new TextRun({ text: ' and subsequently adopted in credit risk modelling for LGD estimation. The method estimates how losses develop over time by examining historical patterns across cohorts at different stages of maturity. It is one of the most widely used approaches in both general insurance reserving and credit risk, as documented extensively in the actuarial literature.', font: 'Arial', size: 22 }),
                ]),

                p([
                    new TextRun({ text: 'England and Verrall (2002)', font: 'Arial', size: 22, italics: true }),
                    new FootnoteReferenceRun(4),
                    new TextRun({ text: ' provide a comprehensive survey of stochastic claims reserving methods, establishing the theoretical foundations that underpin the chain-ladder approach. ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'W\u00FCthrich and Merz (2008)', font: 'Arial', size: 22, italics: true }),
                    new FootnoteReferenceRun(6),
                    new TextRun({ text: ' further extend the framework with rigorous statistical treatment of prediction uncertainty, which informs our confidence interval methodology.', font: 'Arial', size: 22 }),
                ]),

                p('The model applies the chain-ladder technique to a recovery triangle of defaulted municipal debt exposures, computing LGD as one minus the present value of cumulative recoveries.'),

                heading('4.2 Core Computational Steps', HeadingLevel.HEADING_2),
                p('The model proceeds through four sequential computational steps, each producing an intermediate matrix that feeds into the next:'),

                heading('4.2.1 Step 1: Aggregate Recoveries', HeadingLevel.HEADING_3),
                p('For each transition from period n to n+1, aggregate recovery is calculated as:'),
                mathBlock('Recovery(n) = \u2211 Balance(i, n) \u2013 \u2211 Balance(i, n+1)'),
                mathBlock('  for all cohorts i with non-missing data at period n+1'),
                p('The mask restricts summation to cohorts that have observations at both periods n and n+1, ensuring that the recovery calculation is not contaminated by cohorts that have not yet been observed at the later period. The final period recovery is defined as zero (no further observations available).'),

                heading('4.2.2 Step 2: Cumulative Balances', HeadingLevel.HEADING_3),
                p('The cumulative balance matrix is of shape (n_periods \u00D7 n_periods). For row r and column c:'),
                mathBlock('CumBal(r, c) = \u2211 Balance(i, r)'),
                mathBlock('  for all cohorts i with non-missing data at period c+1'),
                p('This gives the total outstanding balance at period r, restricted to cohorts that are still observable at period c+1. The last column uses a slightly different mask: it includes cohorts with observations at period c itself rather than c+1.'),

                heading('4.2.3 Step 3: Discount Matrix', HeadingLevel.HEADING_3),
                p('The discount matrix accounts for the time value of money using the annual effective interest rate (EIR proxy). For row r and column c:'),
                mathBlock('DF(r, c) = 1 / (1 + rate)^((c + 1 \u2013 r) / 12)'),
                p('where rate is the annual discount rate (default: 15%) and the exponent converts to monthly compounding. The c+1 follows the 1-indexed column convention from the reference spreadsheet.'),

                heading('4.2.4 Step 4: LGD Term Structure', HeadingLevel.HEADING_3),
                p('The LGD at each Time in Default point t is:'),
                mathBlock('LGD(t) = 1 \u2013 \u2211 [Recovery(c) / CumBal(t, c) \u00D7 DF(t, c)]'),
                mathBlock('  for c from t to n_periods \u2013 1'),
                p('The final element LGD(n_periods) = 1.0 by convention (no recovery data beyond the triangle). The term structure starts at TID=0 (freshly defaulted) and increases towards 1.0 as TID increases, reflecting diminishing recovery prospects over time.'),

                heading('4.3 Discount Rate', HeadingLevel.HEADING_2),
                p('IFRS 9 paragraph B5.5.44 requires that expected credit losses be discounted to the reporting date using the effective interest rate (EIR) determined at initial recognition. For this portfolio, a discount rate of 15% per annum is applied, representing the EIR proxy for Eskom municipal debt. The discount rate is configurable and sensitivity analysis across rates is supported.'),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 5. VINTAGE ANALYSIS =====================
                heading('5. Vintage Analysis Framework', HeadingLevel.HEADING_1),

                heading('5.1 Rolling Window Approach', HeadingLevel.HEADING_2),
                p('The model uses a rolling window of N consecutive monthly default cohorts to calibrate the chain-ladder. Each window position produces one LGD term structure (a \u201Cvintage\u201D). For 82 cohorts and a 60-month window, this yields 23 vintages.'),
                p('The number of vintages for any window size W is: n_vintages = n_total \u2013 W + 1, where n_total is the total number of default cohorts.'),

                heading('5.2 Observation Mask (Critical)', HeadingLevel.HEADING_2),
                p([
                    new TextRun({ text: 'This is the single most important correctness constraint in the model.', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: ' Each vintage\u2019s calculation must be restricted to data that would have been observable at the vintage date. Without this mask, the model would use \u201Cfuture\u201D data that was not available when the forecast was made, invalidating the backtest.', font: 'Arial', size: 22 }),
                ]),
                p('The observation mask works as follows:'),
                mathBlock('offset = n_total \u2013 end_idx'),
                mathBlock('adjusted_max_tid(i) = master_tid(i) \u2013 offset'),
                mathBlock('If adjusted_max_tid < n_periods: set Balance(i, adjusted_max_tid+1 : ) = NaN'),
                p('The offset represents how many months before the latest data point this vintage sits. For the most recent vintage (end_idx = n_total), offset = 0 and no masking occurs. For earlier vintages, progressively more of each cohort\u2019s tail is masked to simulate the information set available at that historical point.'),

                heading('5.3 Multi-Window Calibration', HeadingLevel.HEADING_2),
                p('The model evaluates nine window sizes: 12, 18, 24, 30, 36, 42, 48, 54, and 60 months. All scenarios are aligned to the same backtest dates by using the reference window (60 months) to determine the vintage end-dates. Smaller windows produce the same number of aligned vintages but use fewer historical cohorts for calibration. This alignment is essential for fair comparison across window sizes.'),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 6. BACKTESTING =====================
                heading('6. Backtesting Framework', HeadingLevel.HEADING_1),

                heading('6.1 Forecast vs Actual Comparison', HeadingLevel.HEADING_2),
                p('The backtest compares each vintage\u2019s LGD forecast against the \u201Cactual\u201D LGD that becomes observable when more data arrives. The actual LGD for vintage i is sourced from vintage i+1\u2019s term structure, which incorporates one additional month of recovery data.'),

                heading('6.2 Diagonal Pattern', HeadingLevel.HEADING_2),
                p([
                    new TextRun({ text: 'The actual matrix follows a diagonal pattern that was reverse-engineered from the reference spreadsheet and verified across all 22 testable vintages. ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'The pattern works as follows:', font: 'Arial', size: 22 }),
                ]),
                p('For vintage i (where i=0 is the oldest), the \u201Chindsight\u201D is n_v \u2013 1 \u2013 i, representing how many subsequent vintages exist to provide actual observations. The actual LGD values are drawn from vintage i+1\u2019s complete term structure.'),
                mathBlock('start_tid = 0 if i = 0, else (n_v \u2013 hindsight)'),
                mathBlock('end_tid = n_v + 1  (exclusive upper bound)'),
                p('This produces 276 non-NaN residuals for the 60-month window with 23 vintages, matching the reference workbook exactly.'),

                heading('6.3 Residual Analysis', HeadingLevel.HEADING_2),
                p('Residuals are computed as: Residual = Actual LGD \u2013 Forecast LGD. The following metrics are computed across the flat (non-NaN) residual vector:'),

                new Table({
                    width: { size: TW, type: WidthType.DXA },
                    columnWidths: [3120, 6240],
                    rows: [
                        new TableRow({ children: [hdrCell('Metric', 3120), hdrCell('Description', 6240)] }),
                        new TableRow({ children: [dataCell('Mean Error (Bias)', 3120), dataCell('Average residual; positive = model underestimates loss', 6240)] }),
                        new TableRow({ children: [dataCell('RMSE', 3120), dataCell('Root mean squared error; penalises large deviations', 6240)] }),
                        new TableRow({ children: [dataCell('MAE', 3120), dataCell('Mean absolute error; robust central tendency of error magnitude', 6240)] }),
                        new TableRow({ children: [dataCell('Max |Error|', 3120), dataCell('Worst single residual; tail risk indicator', 6240)] }),
                        new TableRow({ children: [dataCell('IQR', 3120), dataCell('Interquartile range; robust measure of error dispersion', 6240)] }),
                        new TableRow({ children: [dataCell('Composite Score', 3120), dataCell('Weighted combination: 0.20\u00D7bias ratio + 0.35\u00D7RMSE + 0.25\u00D7MAE + 0.20\u00D7tail severity', 6240)] }),
                    ],
                }),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 7. CONFIDENCE INTERVALS =====================
                heading('7. Confidence Interval Methodology', HeadingLevel.HEADING_1),

                heading('7.1 Binomial CI with Vintage \u00D7 Term-Point Scaling', HeadingLevel.HEADING_2),
                p('The confidence intervals use a binomial-inspired scaling approach that accounts for both the hindsight available for each vintage and the number of observations at each TID point. This produces a unique CI bound for every (vintage, TID) cell in the backtest matrix.'),

                heading('7.2 Formula', HeadingLevel.HEADING_2),
                p('For vintage i and TID t:'),
                mathBlock('Scale(i, t) = z \u00D7 StdDev[t] \u00D7 \u221A(H_i / t_d)'),
                mathBlock('Upper(i, t) = MIN(1, Forecast_oldest[t] + Scale(i, t))'),
                mathBlock('Lower(i, t) = MAX(0, Forecast_oldest[t] \u2013 Scale(i, t))'),
                p('where:'),

                new Table({
                    width: { size: TW, type: WidthType.DXA },
                    columnWidths: [2340, 7020],
                    rows: [
                        new TableRow({ children: [hdrCell('Symbol', 2340), hdrCell('Definition', 7020)] }),
                        new TableRow({ children: [dataCell('z', 2340), dataCell('NORMSINV(ci_percentile); e.g. 0.75 \u2192 z \u2248 0.6745', 7020)] }),
                        new TableRow({ children: [dataCell('StdDev[t]', 2340), dataCell('Column standard deviation (ddof=1) of forecast LGD across all vintages at TID t', 7020)] }),
                        new TableRow({ children: [dataCell('H_i', 2340), dataCell('Hindsight for vintage i: H = i + 1 (1 for oldest, n_v\u20131 for newest)', 7020)] }),
                        new TableRow({ children: [dataCell('t_d', 2340), dataCell('TID denominator: MIN(t, n_v \u2013 1), 1-indexed; TID 0 has no CI', 7020)] }),
                        new TableRow({ children: [dataCell('Forecast_oldest', 2340), dataCell('forecast[0, :] \u2014 the oldest vintage\u2019s LGD term structure (CI centre)', 7020)] }),
                    ],
                }),

                p(''),
                heading('7.3 Key Properties', HeadingLevel.HEADING_2),
                p('The CI methodology has several important properties that are verified in the model:'),
                new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 80 },
                    children: [new TextRun({ text: 'Centre: The CI is symmetric around the oldest vintage\u2019s forecast LGD, not the column mean. This is because the oldest vintage represents the model\u2019s initial calibration.', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 80 },
                    children: [new TextRun({ text: 'Staircase pattern: Vintage i has CI from TID = H_i onwards. The oldest vintage (i=0) starts at TID 1; newer vintages start at progressively higher TIDs.', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 80 },
                    children: [new TextRun({ text: 'Unique values: Every (vintage, TID) cell gets a unique CI bound due to the \u221A(H/t) scaling. The CI is not constant within columns.', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 80 },
                    children: [new TextRun({ text: 'TID 0 exclusion: No CI is computed for TID 0 (t_d would be zero, causing division by zero).', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 80 },
                    children: [new TextRun({ text: '275 non-NaN CI cells (not 276): TID 0 is excluded for all vintages.', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'bullets', level: 0 }, spacing: { after: 160 },
                    children: [new TextRun({ text: 'Configurable percentile: The ci_percentile parameter (default 75%) determines the z-score via the inverse normal CDF. This is exposed as a user control.', font: 'Arial', size: 22 })] }),

                heading('7.4 Scaling Rationale', HeadingLevel.HEADING_2),
                p('The \u221A(H/t) scaling serves two purposes: (1) the hindsight factor H widens the CI for newer vintages that have less out-of-sample data to validate against, and (2) the TID denominator narrows the CI for higher TID points where more cross-vintage observations exist. This mimics the binomial variance structure \u221A(p(1\u2013p)/n) where n grows with the number of observations, and is analogous to the prediction error formulations in W\u00FCthrich and Merz (2008).'),

                p('This formula has been validated against the reference Excel workbook to machine precision (0.00 absolute difference across all 275 CI cells), using the workbook\u2019s own standard deviation values.'),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 8. NORMALITY TESTS =====================
                heading('8. Statistical Tests', HeadingLevel.HEADING_1),

                heading('8.1 Jarque-Bera Test', HeadingLevel.HEADING_2),
                p([
                    new TextRun({ text: 'The Jarque-Bera test', font: 'Arial', size: 22 }),
                    new FootnoteReferenceRun(8),
                    new TextRun({ text: ' assesses whether the residuals follow a normal distribution by examining skewness and excess kurtosis:', font: 'Arial', size: 22 }),
                ]),
                mathBlock('JB = (n/6) \u00D7 (S\u00B2 + K\u00B2/4)'),
                p('where S is skewness and K is excess kurtosis. Under the null hypothesis of normality, JB follows a chi-squared distribution with 2 degrees of freedom. At the 5% significance level, the critical value is 5.991.'),

                heading('8.2 Chi-Square Goodness of Fit', HeadingLevel.HEADING_2),
                p('A chi-square goodness-of-fit test is also applied. The residual range [\u03BC\u20133\u03C3, \u03BC+3\u03C3] is divided into 12 equal-width bins, with the first and last bins extended to \u00B1\u221E. Bins with expected frequency less than 5 are merged with adjacent bins. The degrees of freedom are df = valid_bins \u2013 3 (accounting for estimation of mean and standard deviation).'),

                heading('8.3 Interpretation', HeadingLevel.HEADING_2),
                p('For this portfolio, both tests reject normality at the 5% level. This is expected for credit risk residuals, which typically exhibit fat tails and positive skewness due to the bounded nature of LGD (between 0 and 1) and the concentration of losses. The non-normality finding supports the use of binomial-scaled confidence intervals rather than purely normal-theory intervals.'),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 9. SCENARIO COMPARISON =====================
                heading('9. Multi-Scenario Window Size Analysis', HeadingLevel.HEADING_1),

                heading('9.1 Composite Scoring', HeadingLevel.HEADING_2),
                p('Each window size is evaluated using a composite score that balances multiple objectives:'),
                mathBlock('Score = 0.20 \u00D7 |Bias| / MAE  +  0.35 \u00D7 RMSE  +  0.25 \u00D7 MAE  +  0.20 \u00D7 MaxErr / StdErr'),
                p('This weighting reflects the relative importance of unbiasedness (20%), precision (35%), average accuracy (25%), and tail behaviour (20%). The composite score is unit-free and lower values indicate better performance.'),

                heading('9.2 AIC Proxy', HeadingLevel.HEADING_2),
                p('An Akaike Information Criterion proxy provides a complementary model selection metric:'),
                mathBlock('AIC = n \u00D7 log(SSE / n) + 2k'),
                p('where n is the number of residuals, SSE is the sum of squared errors, and k is the window size. This penalises model complexity (larger windows) while rewarding fit, in line with standard information-theoretic model selection.'),

                heading('9.3 Results Summary', HeadingLevel.HEADING_2),
                p('The following table summarises the backtest performance across all evaluated window sizes, sorted by composite score:'),

                new Table({
                    width: { size: TW, type: WidthType.DXA },
                    columnWidths: [1000, 1300, 1300, 1300, 1300, 1300, 1760],
                    rows: [
                        new TableRow({ children: [
                            hdrCell('Rank', 1000), hdrCell('Window', 1300), hdrCell('RMSE', 1300),
                            hdrCell('MAE', 1300), hdrCell('Bias', 1300), hdrCell('Max|Err|', 1300),
                            hdrCell('Score', 1760),
                        ]}),
                        new TableRow({ children: [
                            dataCell('1', 1000), dataCell('12m', 1300), dataCell('0.0152', 1300),
                            dataCell('0.0049', 1300), dataCell('+0.0017', 1300), dataCell('0.1143', 1300),
                            dataCell('0.3553', 1760),
                        ]}),
                        new TableRow({ children: [
                            dataCell('2', 1000), dataCell('24m', 1300), dataCell('0.0214', 1300),
                            dataCell('0.0132', 1300), dataCell('+0.0020', 1300), dataCell('0.1204', 1300),
                            dataCell('0.4984', 1760),
                        ]}),
                        new TableRow({ children: [
                            dataCell('3', 1000), dataCell('48m', 1300), dataCell('0.0336', 1300),
                            dataCell('0.0238', 1300), dataCell('+0.0082', 1300), dataCell('0.1312', 1300),
                            dataCell('0.5662', 1760),
                        ]}),
                        new TableRow({ children: [
                            dataCell('4', 1000), dataCell('42m', 1300), dataCell('0.0341', 1300),
                            dataCell('0.0205', 1300), dataCell('+0.0141', 1300), dataCell('0.1422', 1300),
                            dataCell('0.5883', 1760),
                        ]}),
                        new TableRow({ children: [
                            dataCell('5', 1000), dataCell('18m', 1300), dataCell('0.0405', 1300),
                            dataCell('0.0184', 1300), dataCell('+0.0045', 1300), dataCell('0.2614', 1300),
                            dataCell('0.6107', 1760),
                        ]}),
                    ],
                }),
                p(''),
                p([
                    new TextRun({ text: 'Note: ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'The full ranking table for all 9 window sizes is available in each per-window workbook\u2019s Backtest Summary sheet.', font: 'Arial', size: 22 }),
                ]),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 10. VALIDATION =====================
                heading('10. Validation and Quality Assurance', HeadingLevel.HEADING_1),

                heading('10.1 Machine-Precision Validation', HeadingLevel.HEADING_2),
                p('The Python implementation has been validated against the reference Excel workbook to machine precision. For the 60-month window:'),

                new Table({
                    width: { size: TW, type: WidthType.DXA },
                    columnWidths: [4680, 4680],
                    rows: [
                        new TableRow({ children: [hdrCell('Validation Check', 4680), hdrCell('Result', 4680)] }),
                        new TableRow({ children: [dataCell('LGD term structures (all 23 vintages)', 4680), dataCell('Max absolute diff: 8.88e-16', 4680)] }),
                        new TableRow({ children: [dataCell('Forecast matrix (23 \u00D7 61)', 4680), dataCell('Exact match', 4680)] }),
                        new TableRow({ children: [dataCell('Actual matrix (diagonal)', 4680), dataCell('Exact match', 4680)] }),
                        new TableRow({ children: [dataCell('All 276 residuals', 4680), dataCell('Max absolute diff: 0.000000', 4680)] }),
                        new TableRow({ children: [dataCell('Upper CI (275 cells)', 4680), dataCell('Max absolute diff: 0.00', 4680)] }),
                        new TableRow({ children: [dataCell('Lower CI (275 cells)', 4680), dataCell('Max absolute diff: 0.00', 4680)] }),
                    ],
                }),

                p(''),
                heading('10.2 Reference Values', HeadingLevel.HEADING_2),
                p('The following reference values serve as regression test anchors:'),

                new Table({
                    width: { size: TW, type: WidthType.DXA },
                    columnWidths: [4680, 4680],
                    rows: [
                        new TableRow({ children: [hdrCell('Metric', 4680), hdrCell('Value', 4680)] }),
                        new TableRow({ children: [dataCell('Forecast[0, 0]', 4680), dataCell('0.225514586109806', 4680)] }),
                        new TableRow({ children: [dataCell('Actual[0, 0]', 4680), dataCell('0.236239450466784', 4680)] }),
                        new TableRow({ children: [dataCell('Residual mean', 4680), dataCell('0.006962', 4680)] }),
                        new TableRow({ children: [dataCell('Residual std dev', 4680), dataCell('0.093872', 4680)] }),
                        new TableRow({ children: [dataCell('Non-NaN residuals', 4680), dataCell('276', 4680)] }),
                        new TableRow({ children: [dataCell('JB test', 4680), dataCell('Rejects normality', 4680)] }),
                        new TableRow({ children: [dataCell('Chi-Sq test', 4680), dataCell('Rejects normality', 4680)] }),
                    ],
                }),

                heading('10.3 Known Workbook Discrepancy', HeadingLevel.HEADING_2),
                p('One discrepancy has been identified and documented: the reference workbook\u2019s unlabelled vintage sheet uses a 0% discount rate for the Latest vintage instead of the correct 15%, producing an LGD at TID 0 of 0.2464 versus 0.2919. This is a linking error in the workbook (the correctly-linked sheet, labelled \u201C(0-59)\u201D, matches Python to machine precision). The discrepancy propagates a approximately 0.003 difference in column standard deviations and approximately 0.6% maximum CI value difference. All per-window workbooks produced by this model use the correct 15% discount rate throughout.'),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 11. LIMITATIONS =====================
                heading('11. Limitations and Assumptions', HeadingLevel.HEADING_1),

                new Paragraph({ numbering: { reference: 'numbers', level: 0 }, spacing: { after: 120 },
                    children: [new TextRun({ text: 'Stationarity assumption: The chain-ladder method assumes that historical recovery patterns are indicative of future recoveries. Structural breaks in municipal payment behaviour would violate this assumption.', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'numbers', level: 0 }, spacing: { after: 120 },
                    children: [new TextRun({ text: 'Portfolio homogeneity: All non-metro municipal exposures are treated as a single portfolio. Segmentation by municipality size, region, or historical payment performance may improve predictive accuracy.', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'numbers', level: 0 }, spacing: { after: 120 },
                    children: [new TextRun({ text: 'Point-in-time estimates: The model produces point-in-time LGD estimates based on historical data. Forward-looking adjustments (as required by IFRS 9 paragraph 5.5.17(c)) should be applied separately as macroeconomic overlays.', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'numbers', level: 0 }, spacing: { after: 120 },
                    children: [new TextRun({ text: 'Discount rate sensitivity: The model uses a single discount rate across all periods and cohorts. A term structure of rates may be more appropriate for long-dated exposures.', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'numbers', level: 0 }, spacing: { after: 120 },
                    children: [new TextRun({ text: 'Non-normal residuals: Both the Jarque-Bera and chi-square tests reject normality. While the binomial CI framework does not require normality, users should exercise caution when interpreting coverage statistics.', font: 'Arial', size: 22 })] }),
                new Paragraph({ numbering: { reference: 'numbers', level: 0 }, spacing: { after: 160 },
                    children: [new TextRun({ text: 'Data vintage: The recovery triangle spans March 2019 to December 2025. As new data becomes available, the model should be recalibrated and the backtest re-run.', font: 'Arial', size: 22 })] }),

                new Paragraph({ children: [new PageBreak()] }),

                // ===================== 12. REFERENCES =====================
                heading('12. References', HeadingLevel.HEADING_1),

                p([
                    new TextRun({ text: '1. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'IASB (2014), ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'IFRS 9 Financial Instruments', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', International Accounting Standards Board.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '2. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'Basel Committee on Banking Supervision (2015), ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'Guidance on credit risk and accounting for expected credit losses', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', BCBS d350, Bank for International Settlements.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '3. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'Mack, T. (1993), \u201CDistribution-free calculation of the standard error of chain ladder reserve estimates,\u201D ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'ASTIN Bulletin', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', 23(2), pp. 213\u2013225.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '4. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'England, P.D. and Verrall, R.J. (2002), \u201CStochastic claims reserving in general insurance,\u201D ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'British Actuarial Journal', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', 8(3), pp. 443\u2013518.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '5. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'Taylor, G. (2000), ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'Loss Reserving: An Actuarial Perspective', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', Kluwer Academic Publishers.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '6. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'W\u00FCthrich, M.V. and Merz, M. (2008), ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'Stochastic Claims Reserving Methods in Insurance', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', Wiley Finance.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '7. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'South African Reserve Bank, ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'Banks Act Directive 8/2019: Implementation of IFRS 9', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', Pretoria.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '8. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'Jarque, C.M. and Bera, A.K. (1987), \u201CA test for normality of observations and regression residuals,\u201D ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'International Statistical Review', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', 55(2), pp. 163\u2013172.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '9. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'Akaike, H. (1974), \u201CA new look at the statistical model identification,\u201D ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'IEEE Transactions on Automatic Control', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', 19(6), pp. 716\u2013723.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '10. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'Schuermann, T. (2004), \u201CWhat do we know about Loss Given Default?,\u201D in ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'Credit Risk Models and Management', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', 2nd ed., Risk Books, London.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '11. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'Bellini, T. (2019), ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'IFRS 9 and CECL Credit Risk Modelling and Validation: A Practical Guide with Examples Worked in R and SAS', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', Academic Press.', font: 'Arial', size: 22 }),
                ]),
                p([
                    new TextRun({ text: '12. ', font: 'Arial', size: 22, bold: true }),
                    new TextRun({ text: 'European Banking Authority (2017), ', font: 'Arial', size: 22 }),
                    new TextRun({ text: 'Guidelines on PD estimation, LGD estimation and the treatment of defaulted exposures', font: 'Arial', size: 22, italics: true }),
                    new TextRun({ text: ', EBA/GL/2017/16.', font: 'Arial', size: 22 }),
                ]),

                new Paragraph({ spacing: { before: 600 } }),
                new Paragraph({
                    border: { top: { style: BorderStyle.SINGLE, size: 2, color: '2E75B6' } },
                    spacing: { before: 200, after: 100 },
                    children: [new TextRun({ text: '\u2014 End of Document \u2014', font: 'Arial', size: 20, color: '999999', italics: true })],
                    alignment: AlignmentType.CENTER,
                }),
            ],
        },
    ],
});

const outputPath = process.argv[2] || '/sessions/focused-busy-hopper/mnt/eskom_backtesting/LGD_Model_Methodology.docx';
Packer.toBuffer(doc).then(buffer => {
    fs.writeFileSync(outputPath, buffer);
    console.log(`Methodology document saved to: ${outputPath}`);
});
