import pandas as pd
import numpy as np
import warnings
import argparse
from collections import Counter
from sklearn.linear_model import LinearRegression
parser = argparse.ArgumentParser()

args = parser.parse_args()

warnings.simplefilter(action='ignore', category=Warning)

state_df = pd.read_csv("walker_warnock_precinct_november.csv", dtype={'County Precinct': object})
state_df['County'] = state_df["County"].map(lambda x: x.title())
precinct_splits_df = pd.read_csv('precinct_breakdowns/precinct_breakdowns_2022.csv', header=0, sep=',')

counties = sorted(state_df['County'].unique())
county_id = 0
results_df = None
eday_modifier = 1.0

white_shares = None
master_df = None
warnock_adv_votes, warnock_mail_votes = 0, 0
walker_adv_votes, walker_mail_votes = 0, 0
calc_warnock_adv_votes, calc_warnock_mail_votes = 0, 0
calc_walker_adv_votes, calc_walker_mail_votes = 0, 0

# For each precinct:
# 1. calculate the number of votes cast in November and the dem share, both stratified by mode.
# 2. also calculate the number of registered voters per race. store -1 if no racial informaton.
# 3. then, calculate the number of votes cast by each race based on statewide turnout shares. if nothing there, then -1 here
# 4. then, sum up the number of votes cast by each race and then normalize for the true number of votes cast.
# 5. calculate the white share of the vote for the precinct.
#      - if the white share < 3, drop Black turnout by 2% from the statewide turnout share table, repeat steps 3-5.
#      - if the white share > 85, raise Black turnout by 2% from the statewide turnout share table, repeat steps 3-5.
# 6. divide the number of votes cast by each race by the number of total votes to get county racial turnout details. 0 if no info.
# 7. For each precinct, export:
#      - county, precinct code, November racial shares, racial support splits
num_retries = 0
precinct_lst = []
for county_name in counties:
    county_id += 1
    county_df = state_df[state_df["County"] == county_name]
    precinct_df = precinct_splits_df[precinct_splits_df["county_code"] == county_id]
    precinct_df['County'] = county_name
    splits_df = county_df.groupby(["County", "County Precinct"], as_index=False).sum()

    # FOR NOVEMBER:
    # 1) calculate turnout per race by multiplying the number of registered voters of a race by turnout per mode
    # 2) normalize turnout per race to true # of votes cast
    # 3) calculate democratic share of whites PER MODE by doing (dem_votes - 0.8 * black + 0.24 * all_others) / total_votes
    # 4) save the per mode splits per precinct to a csv.

    ###### Begin November Early Voting Data Computation #####

    # November Early In Person Voting
    splits_df["nov_adv_votes"] = splits_df["Warnock Advance Voting Votes"] + splits_df["Walker Advance Voting Votes"]
    splits_df["dem_adv_share"] = splits_df["Warnock Advance Voting Votes"] / splits_df["nov_adv_votes"]

    # November Vote by Mail
    splits_df["nov_vbm_votes"] = splits_df["Warnock Absentee by Mail Votes"] + splits_df["Walker Absentee by Mail Votes"]
    splits_df["dem_vbm_share"] = splits_df["Warnock Absentee by Mail Votes"] / splits_df["nov_vbm_votes"]

    # merge splits with the precinct df
    merged_precinct_df = precinct_df.merge(splits_df, how='right', left_on=['County', 'county_precinct_id'], right_on=['County', 'County Precinct'])
    merged_precinct_df = merged_precinct_df.fillna('unknown')

    county_precincts = []
    # now you have a bunch of precincts with racial splits. let's now calculate the number of votes cast by each race based on statewide turnout shares.
    for precinct_code in merged_precinct_df['County Precinct'].unique():
        racial_margins_defaults = pd.read_csv('statewide_splits/racial_margins_defaults.csv', header=0, sep=',')
        racial_turnout_splits_df = pd.read_csv('statewide_splits/racial_turnout_rates_by_mode.csv', header=0, sep=',')
        single_precinct_info_df = merged_precinct_df[merged_precinct_df['county_precinct_id'] == precinct_code]
        precinct_info = dict()
        precinct_info['County'] = county_name
        precinct_info['County Precinct'] = precinct_code
        # step 3, 4, 5 here.
        true_precinct_mail_votes = single_precinct_info_df['nov_vbm_votes'].values[0]
        true_precinct_adv_votes = single_precinct_info_df['nov_adv_votes'].values[0]
        true_dem_adv_votes = splits_df.loc[splits_df['County Precinct'] == precinct_code, "Warnock Advance Voting Votes"].values[0]
        true_dem_mail_votes = splits_df.loc[splits_df['County Precinct'] == precinct_code, "Warnock Absentee by Mail Votes"].values[0]
        true_dem_mail_share = true_dem_mail_votes / true_precinct_mail_votes
        true_dem_adv_share = true_dem_adv_votes / true_precinct_adv_votes
        optimum = False
        added = False
        while not optimum:
            estimated_mail_votes = 0
            estimated_adv_votes = 0
            for race in single_precinct_info_df['race'].values:
                # get race turnout by mode
                race_turnout_rate_mail = racial_turnout_splits_df.loc[racial_turnout_splits_df['race'] == race, 'nov_mail_rate'].values[0]
                race_turnout_rate_adv = racial_turnout_splits_df.loc[racial_turnout_splits_df['race'] == race, 'nov_early_in_person_rate'].values[0]
                num_race_voters = single_precinct_info_df.loc[single_precinct_info_df['race'] == race, 'registered_voters'].values[0]
                race_mail_votes = num_race_voters * race_turnout_rate_mail
                race_adv_votes = num_race_voters * race_turnout_rate_adv
                precinct_info[race + '_mail_votes'] = race_mail_votes
                precinct_info[race + '_adv_votes'] = race_adv_votes
                # sum up estimated votes cast
                estimated_mail_votes += race_mail_votes
                estimated_adv_votes += race_adv_votes

            # step 4: normalize
            mail_normalization = true_precinct_mail_votes / estimated_mail_votes
            adv_normalization = true_precinct_adv_votes / estimated_adv_votes

            dem_mail_votes = 0.0
            dem_adv_votes = 0.0
            for race in single_precinct_info_df['race'].values:
                race_support_rate = racial_margins_defaults.loc[racial_margins_defaults['race'] == race, 'share'].values[0]
                precinct_info[race + '_mail_votes'] *= mail_normalization
                precinct_info[race + '_adv_votes'] *= adv_normalization
                if race != 'white':
                    dem_mail_votes += precinct_info[race + '_mail_votes'] * race_support_rate
                    dem_adv_votes += precinct_info[race + '_adv_votes'] * race_support_rate
                    # 6. store the support shares and turnout rates per demographic in the dictionary for the precinct.
                    precinct_info[race + '_mail_support_share'] = race_support_rate
                    precinct_info[race + '_adv_support_share'] = race_support_rate
                    precinct_info[race + '_mail_turnout_share'] = precinct_info[race + '_mail_votes'] / true_precinct_mail_votes
                    precinct_info[race + '_adv_turnout_share'] = precinct_info[race + '_adv_votes'] / true_precinct_adv_votes

            white_dem_adv_votes = true_dem_adv_votes - dem_adv_votes
            white_dem_mail_votes = true_dem_mail_votes - dem_mail_votes
            if 'white' in single_precinct_info_df['race'].values:
                precinct_info['white_mail_support_share'] = min(1, max(0, white_dem_mail_votes / precinct_info['white_mail_votes']))
                precinct_info['white_adv_support_share'] = min(1, max(0, white_dem_adv_votes / precinct_info['white_adv_votes']))
                precinct_info['white_mail_turnout_share'] = min(1, max(0, precinct_info['white_mail_votes'] / true_precinct_mail_votes))
                precinct_info['white_adv_turnout_share'] = min(1, max(0, precinct_info['white_adv_votes'] / true_precinct_adv_votes))
                num_whites = single_precinct_info_df.loc[single_precinct_info_df['race'] == 'white', 'registered_voters'].values[0]
            else:
                precinct_info['white_mail_support_share'] = 0
                precinct_info['white_adv_support_share'] = 0
                precinct_info['white_mail_turnout_share'] = 0
                precinct_info['white_adv_turnout_share'] = 0
                num_whites = 0
            retry = False

            # don't want to start tuning on precincts that are too small
            mail_size_filters = true_dem_mail_votes > 50
            adv_size_filters = true_dem_adv_votes > 50
            rate_filters = (true_dem_mail_votes / true_precinct_mail_votes) < 0.9
            if precinct_info['white_mail_support_share'] < 0.02 and white_dem_mail_votes < -1 and mail_size_filters:
                racial_turnout_splits_df.loc[racial_turnout_splits_df['race'] == 'white', 'nov_mail_rate'] += 0.25
                racial_margins_defaults.loc[racial_margins_defaults['race'] == 'black', 'share'] = (racial_margins_defaults.loc[racial_margins_defaults['race'] == 'black', 'share'] - 0.01).clip(0.8, 0.98)
                racial_margins_defaults.loc[racial_margins_defaults['race'] == 'other', 'share'] = (racial_margins_defaults.loc[racial_margins_defaults['race'] == 'other', 'share'] - 0.20).clip(0.1, 0.9)
                print("Mail less in", county_name, precinct_code, precinct_info['white_mail_support_share'], num_whites)
                retry = True
            elif precinct_info['white_mail_support_share'] > 0.90 and precinct_info['white_mail_support_share'] > true_dem_mail_share and mail_size_filters and white_dem_mail_votes > 20:
                racial_turnout_splits_df.loc[racial_turnout_splits_df['race'] == 'black', 'nov_mail_rate'] += 0.30
                racial_turnout_splits_df.loc[racial_turnout_splits_df['race'] == 'other', 'nov_mail_rate'] += 0.30
                racial_margins_defaults.loc[racial_margins_defaults['race'] == 'black', 'share'] = (racial_margins_defaults.loc[racial_margins_defaults['race'] == 'black', 'share'] + 0.005).clip(0.8, 0.98)
                racial_margins_defaults.loc[racial_margins_defaults['race'] == 'other', 'share'] = (racial_margins_defaults.loc[racial_margins_defaults['race'] == 'other', 'share'] + 0.20).clip(0.1, racial_margins_defaults.loc[racial_margins_defaults['race'] == 'black', 'share'].values[0])
                print("Mail greater in ", county_name, precinct_code, precinct_info['white_mail_support_share'], num_whites)
                retry = True
            if precinct_info['white_adv_support_share'] < 0.02 and white_dem_adv_votes < -1 and adv_size_filters:
                racial_turnout_splits_df.loc[racial_turnout_splits_df['race'] == 'white', 'nov_early_in_person_rate'] += 0.30
                racial_margins_defaults.loc[racial_margins_defaults['race'] == 'black', 'share'] -= 0.01
                racial_margins_defaults.loc[racial_margins_defaults['race'] == 'other', 'share'] -= 0.10
                print("Adv less in", county_name, precinct_code, precinct_info['white_adv_support_share'], num_whites)
                retry = True
            elif precinct_info['white_adv_support_share'] > 0.9 and precinct_info['white_adv_support_share'] > true_dem_adv_share and adv_size_filters and white_dem_adv_votes > 20:
                racial_turnout_splits_df.loc[racial_turnout_splits_df['race'] == 'black', 'nov_early_in_person_rate'] += 0.40
                racial_turnout_splits_df.loc[racial_turnout_splits_df['race'] == 'other', 'nov_early_in_person_rate'] += 0.30
                racial_margins_defaults.loc[racial_margins_defaults['race'] == 'black', 'share'] = (racial_margins_defaults.loc[racial_margins_defaults['race'] == 'black', 'share'] + 0.005).clip(0.8, 0.98)
                racial_margins_defaults.loc[racial_margins_defaults['race'] == 'other', 'share'] = (racial_margins_defaults.loc[racial_margins_defaults['race'] == 'other', 'share'] + 0.20).clip(0.1, racial_margins_defaults.loc[racial_margins_defaults['race'] == 'black', 'share'].values[0])
                print("Adv greater in ", county_name, precinct_code, precinct_info['white_adv_support_share'], num_whites)
                retry = True
            if not retry:
                optimum = True
            else:
                if not added:
                    num_retries += 1
                    added = True
        cols_to_keep = ['County', 'County Precinct']
        for race in single_precinct_info_df['race'].values:
            cols_to_keep += [race + '_mail_turnout_share', race + '_adv_turnout_share']
            cols_to_keep += [race + '_mail_support_share', race + '_adv_support_share']
        county_precincts += [{key: precinct_info[key] for key in cols_to_keep}]

    precinct_lst += county_precincts
    print(f'{county_name} done!')
    print(f'number of current retries: {num_retries}')
precinct_data = pd.DataFrame.from_dict(precinct_lst)
precinct_data.to_csv('precinct_breakdowns/precinct_racial_turnout_partisanship_splits.csv', header=True, sep=',')


