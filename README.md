# 🏎️ Formula 1 Race Data Engineering & Analysis Project

A comprehensive data engineering project that processes, standardizes, and validates Formula 1 race data from multiple sources (2019-2025) for machine learning and predictive analytics.

## 📋 Project Overview

This project consolidates Formula 1 racing data from two primary sources:
- **GitHub Dataset**: Formula 1 historical race results, qualifying sessions, and driver information
- **Kaggle Dataset**: Additional driver metadata, circuit information, and historical records

The goal is to create a clean, standardized, and validated dataset suitable for:
- Race outcome prediction
- Driver performance analysis
- Team performance tracking
- Qualifying vs. race result correlation studies

## 🗂️ Project Structure

```
├── 📁 formula1-datasets-master/        # Raw GitHub F1 datasets (2019-2025)
├── 📁 filler-datasets(kaggle)/         # Kaggle supplementary datasets
├── 📁 main_race_result(processed)/     # Processed main race results
├── 📁 quali_both_result(processed)/    # Processed qualifying results (race & sprint)
├── 📁 sprint_race_result(processed)/   # Processed sprint race results
├── 📁 driver_dataset_final/            # Standardized driver-team mappings by season
├── 📁 cache/                           # FastF1 API cache
├── 📊 dataset_analysis.ipynb           # Initial data exploration & merging
├── 📊 dataset_analysis_second.ipynb    # Qualifying data processing
├── 📊 filler_dataset_analysis.ipynb    # Kaggle dataset integration
├── 📊 missing_dataset_generation.ipynb # Team standardization & missing data
├── 📊 dataset_validation.ipynb         # Data quality validation
└── 📊 f1-pred.ipynb                    # Prediction model exploration
```

## 🔄 Data Processing Pipeline

### 1. **Data Collection & Integration**
- Imported race results, qualifying results, sprint races (2019-2025)
- Merged GitHub and Kaggle datasets using driver name normalization
- Added unique `kaggle_driver_id` for consistent driver tracking

### 2. **Data Cleaning & Standardization**

#### Driver Name Normalization
```python
# Unicode normalization to handle special characters (Räikkönen, Pérez, etc.)
- Lowercase conversion
- Accent removal (NFKD normalization)
- Whitespace standardization
```

#### Team Name Standardization
- Created season-specific driver-team mappings
- Standardized team names across all datasets
- Handled team name changes (e.g., "Racing Point" → "Aston Martin")

#### Time Conversion
- Converted qualifying lap times from `MM:SS.mmm` format to seconds
- Processed race time gaps (e.g., "+5.478s") to numeric values
- Handled DNF (Did Not Finish) and NC (Not Classified) cases

### 3. **Feature Engineering**

#### Main Race Results
```
- Position (final race position)
- Starting Grid (qualifying position)
- kaggle_driver_id (unique driver identifier)
- raceId (unique race identifier)
- finished (1/0 binary)
- dnf (Did Not Finish flag)
- laps_down (laps behind leader)
- time_gap_sec (time gap in seconds)
- Team (standardized team name)
- Track (circuit name)
```

#### Qualifying Results
```
- raceId
- Team
- kaggle_driver_id
- position (qualifying position)
- participated_q2 (binary flag)
- participated_q3 (binary flag)
- q1_time_sec (Q1 lap time in seconds)
- q2_time_sec (Q2 lap time in seconds)
- q3_time_sec (Q3 lap time in seconds)
- Track
```

#### Sprint Race Results
```
- Position
- Starting Grid
- kaggle_driver_id
- raceId
- finished
- dnf
- laps_down
- time_gap_sec
- Team
- Track
```

### 4. **Data Validation**

Comprehensive validation checks implemented:

✅ **Column Consistency**: All datasets have identical column schemas per category  
✅ **Missing Values**: Zero missing values in critical fields (raceId, driver_id, Team, Track)  
✅ **Duplicate Detection**: No duplicate driver entries per race  
✅ **Driver Count Validation**: 19-20 drivers per race (expected range)  
✅ **Qualifying Logic**: Q3 participants always participated in Q2  
✅ **Team Assignment**: All drivers have valid team assignments per season

## 📊 Dataset Statistics

| Dataset Type | Years Covered | Total Races | Total Records |
|-------------|---------------|-------------|---------------|
| Main Races | 2019-2025 | ~160 races | ~3,200 entries |
| Qualifying | 2019-2025 | ~160 sessions | ~3,200 entries |
| Sprint Races | 2021-2025 | ~18 races | ~360 entries |
| Sprint Qualifying | 2023-2025 | ~18 sessions | ~360 entries |

## 🔧 Key Technologies & Libraries

- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computations
- **unicodedata**: Character normalization for international driver names

## 📝 Data Processing Notebooks

### 1. `dataset_analysis.ipynb`
- Initial data exploration of 2024 season
- Driver ID merging between GitHub and Kaggle datasets
- Name normalization implementation
- Basic statistical analysis

### 2. `dataset_analysis_second.ipynb`
- Qualifying data processing (race and sprint)
- RaceID assignment using pointer-based approach
- Time conversion functions
- Sprint qualifying format handling

### 3. `filler_dataset_analysis.ipynb`
- Kaggle dataset filtering (2019+ only)
- Driver, circuit, and race metadata extraction
- Column reduction for relevant features
- Cross-dataset validation

### 4. `missing_dataset_generation.ipynb`
- Season-specific driver-team mapping creation
- Team name standardization across all datasets
- Missing data imputation
- Final dataset export

### 5. `dataset_validation.ipynb`
- Schema consistency validation
- Missing value detection
- Duplicate entry checks
- Logical consistency verification (Q2/Q3 participation)
- Driver count per race validation

## 🤖 Machine Learning Model (In Development)

### Ranking-Based XGBoost for Race Result Prediction

A **Learning-to-Rank XGBoost model** is currently in development to predict individual driver finishing positions in Formula 1 races.

#### Why Ranking-Based Approach?

Traditional regression or classification models treat race positions independently. However, F1 race results are inherently a **ranking problem** where:
- Positions are relative (1st, 2nd, 3rd, etc.)
- The order matters more than absolute values
- Drivers compete against each other, not against a fixed target

#### Planned Model Architecture

**Algorithm**: XGBoost Ranker (`xgboost.XGBRanker`)  
**Objective**: `rank:pairwise` (pairwise ranking loss)  
**Evaluation Metric**: NDCG (Normalized Discounted Cumulative Gain)

#### Planned Features

**Qualifying Performance**:
- Starting grid position
- Q1, Q2, Q3 lap times (in seconds)
- Qualifying session participation flags

**Driver & Team**:
- Driver ID (encoded)
- Team (encoded)
- Historical driver performance

**Circuit Characteristics**:
- Track name (encoded)
- Circuit-specific driver performance

**Historical Performance**:
- Recent race results
- Season-to-date points
- Team performance trends

#### Planned Evaluation Metrics

- **NDCG@10**: Measures ranking quality for top 10 positions
- **Spearman's Rank Correlation**: Correlation between predicted and actual rankings
- **Top-3 Accuracy**: Percentage of correctly predicted podium finishers
- **Mean Absolute Error**: Average position difference

_Note: Model implementation and performance results will be added once development is complete._

## 🎯 Use Cases

This processed dataset and ML model enable:

1. **Race Prediction Models**
   - Predict race outcomes based on qualifying performance
   - Rank drivers by expected finishing position
   - Generate probabilistic race forecasts
   - Factor in team performance, driver history, and circuit characteristics

2. **Driver Performance Analysis**
   - Track driver performance across seasons
   - Compare teammates within same team
   - Analyze qualifying-to-race conversion rates
   - Identify over/under-performers relative to predictions

3. **Team Performance Tracking**
   - Monitor team development across seasons
   - Compare constructor performance
   - Identify team strategy patterns
   - Predict constructor championship outcomes

4. **Circuit Analysis**
   - Identify circuit-specific performance patterns
   - Analyze overtaking opportunities
   - Track weather impact on results
   - Predict track-specific driver advantages

## 🚀 Getting Started

### Prerequisites
```bash
pip install pandas numpy jupyter
```

### Running the Notebooks
```bash
jupyter notebook
```

Navigate to any notebook to explore the data processing pipeline.

### Accessing Processed Data
```python
import pandas as pd

# Load main race results
races_2024 = pd.read_csv('main_race_result(processed)/formula1_2024season_raceResults.csv')

# Load qualifying results
quali_2024 = pd.read_csv('quali_both_result(processed)/race_quali_2024.csv')

# Load sprint results
sprint_2024 = pd.read_csv('sprint_race_result(processed)/sprint_2024_result.csv')
```

## 📈 Data Quality Metrics

- **Completeness**: 100% (no missing critical values)
- **Consistency**: 100% (standardized schemas across years)
- **Accuracy**: Validated against official F1 records
- **Uniqueness**: No duplicate race entries per driver
- **Validity**: All logical constraints satisfied

## 🔍 Key Insights from Data Processing

1. **Driver Name Challenges**: International characters (ä, ö, é) required Unicode normalization
2. **Team Name Evolution**: Teams changed names (Racing Point → Aston Martin in 2021)
3. **Sprint Format Changes**: Sprint qualifying format evolved from 2021 to 2023
4. **Missing Drivers**: Some races had 19 drivers due to injuries/replacements
5. **Data Source Gaps**: Kaggle data ended at 2021, requiring GitHub source for 2022+

## 🤝 Contributing

This is a data engineering project focused on F1 race data preparation. Contributions welcome for:
- Additional data sources integration
- Enhanced feature engineering
- Data quality improvements
- Documentation updates

## 📄 License

This project uses publicly available Formula 1 data. Please respect the original data sources' terms of use.

## 🙏 Acknowledgments

- **Formula 1**: Official race data
- **Kaggle**: Historical F1 datasets
- **GitHub F1 Datasets**: Comprehensive season data (2019-2025)
- **FastF1**: Python library for F1 timing data

## 📧 Contact

For questions or collaboration opportunities, please open an issue in this repository.

---

**Note**: This project is for educational and analytical purposes. All Formula 1 trademarks and data belong to their respective owners.
