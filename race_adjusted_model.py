import pandas as pd
import numpy as np
import warnings
import argparse
from collections import Counter
from sklearn.linear_model import LinearRegression
parser = argparse.ArgumentParser()
parser.add_argument('--adjust', default=False, action='store_true', help="Adjust for Race/Party estimates?")

args = parser.parse_args()

warnings.simplefilter(action='ignore', category=Warning)

state_df = pd.read_csv("walker_warnock_precinct_november.csv", dtype={'County Precinct': object})
precinct_splits_df = pd.read_csv('precinct_breakdowns/precinct_racial_turnout_partisanship_splits.csv', header=0, sep=',').fillna(0)
racial_turnout_splits_df = pd.read_csv('statewide_splits/racial_turnout_rates_by_mode.csv', header=0, sep=',')
state_df['County'] = state_df["County"].map(lambda x: x.title())
adv_scale_constants = {'black': 32.1/28.8, 'white': 54.7/57.4, 'hispanic': 1.8/1.9, 'aapi': 1.8/1.8, 'other': 9.3/9.8, 'native_american': 0.3/0.3}
mail_scale_constants = {'black': 28.8/31.5, 'white': 60.3/55.0, 'hispanic': 1.0/1.6, 'aapi': 1.9/3.0, 'other': 7.9/8.7, 'native_american': 0.2/0.2}

counties = sorted(state_df['County'].unique())
county_id = 0
results_df = None
eday_modifier = 1.15

for county_name in counties:
    county_id += 1
    filename = 'Absentee Files/36372/' + '{:0>3}'.format(county_id) + '.csv'
    single_county_df = pd.read_csv(filename, sep=",", header=0)
    single_county_df = single_county_df[["Application Status", "County Precinct", "Ballot Status", "Status Reason", "Ballot Return Date", "Ballot Style"]]
    single_county_df['County'] = county_name

    ## create a new column that says 1 if the ballot is validly cast, 0 if not
    single_county_df["isValid"] = 0
    single_county_df.loc[single_county_df["Ballot Status"] == "A", "isValid"] = 1

    # Electronic is the same as Mailed
    single_county_df["Ballot Style"] = single_county_df["Ballot Style"].replace("ELECTRONIC", "MAILED")

    county_accept_totals = single_county_df.groupby(["County", "County Precinct", "Ballot Style"]).size().reset_index(name='num_applications')

    ## create a count that sums up the valid votes cast and splits by style
    county_votes_cast_split = single_county_df.groupby(["County", "County Precinct", "Ballot Style"], as_index=False).sum("isValid")
    county_votes_cast_split['County Precinct'] = county_votes_cast_split['County Precinct'].map(lambda x: str(x))

    county_df = state_df[state_df["County"] == county_name]
    splits_df = county_df.groupby(["County", "County Precinct"], as_index=False).sum()

    # precinct splits file
    precinct_df = precinct_splits_df[precinct_splits_df["County"] == county_name]

    # adjust for early vote shift in composition.
    precinct_df['adv_normalization_constant'] = 0
    precinct_df['mail_normalization_constant'] = 0

    for race in adv_scale_constants.keys():
        adv_turnout_rescaled_share = precinct_df[race + '_adv_turnout_share'] * adv_scale_constants[race]
        precinct_df[race + '_adv_turnout_share'] = adv_turnout_rescaled_share
        mail_turnout_rescaled_share = precinct_df[race + '_mail_turnout_share'] * mail_scale_constants[race]
        precinct_df[race + '_mail_turnout_share'] = mail_turnout_rescaled_share
        precinct_df['mail_normalization_constant'] += mail_turnout_rescaled_share
        precinct_df['adv_normalization_constant'] += adv_turnout_rescaled_share

    for race in adv_scale_constants.keys():
        precinct_df[race + '_adv_turnout_share'] /= precinct_df['adv_normalization_constant']
        precinct_df[race + '_mail_turnout_share'] /= precinct_df['mail_normalization_constant']

    # # normalize
    # for race in adv_scale_constants.keys():
    #     precinct_df[race + '_adv_turnout_share'] = precinct_df[race + '_adv_turnout_share'] * adv_scale_constants[race]
    #     precinct_df[race + '_mail_turnout_share'] = precinct_df[race + '_mail_turnout_share'] * mail_scale_constants[race]

    # # adjust for early vote shift in composition.
    # for race in adv_scale_constants.keys():
    #     precinct_df[race + '_adv_turnout_share'] = precinct_df[race + '_adv_turnout_share'] * adv_scale_constants[race]
    #     precinct_df[race + '_mail_turnout_share'] = precinct_df[race + '_mail_turnout_share'] * mail_scale_constants[race]

    ###### Begin November Early Voting Data Computation. TO BE USED FOR IMPUTATION. #####

    # November Early In Person Voting
    splits_df["nov_adv_votes"] = splits_df["Warnock Advance Voting Votes"] + splits_df["Walker Advance Voting Votes"]
    splits_df["dem_nov_adv_share"] = splits_df["Warnock Advance Voting Votes"] / splits_df["nov_adv_votes"]
    splits_df["dem_nov_adv_margin"] = (splits_df["dem_nov_adv_share"] * 2 - 1) * splits_df["nov_adv_votes"]

    # November Vote by Mail
    splits_df["nov_vbm_votes"] = splits_df["Warnock Absentee by Mail Votes"] + splits_df["Walker Absentee by Mail Votes"]
    splits_df["dem_nov_vbm_share"] = splits_df["Warnock Absentee by Mail Votes"] / splits_df["nov_vbm_votes"]
    splits_df["dem_nov_vbm_margin"] = (splits_df["dem_nov_vbm_share"] * 2 - 1) * splits_df["nov_vbm_votes"]
    splits_df["dem_nov_total_ev_margin"] = splits_df["dem_nov_vbm_margin"] + splits_df["dem_nov_adv_margin"]

    # November Election Day
    splits_df["nov_eday_votes"] = splits_df["Warnock Election Day Votes"] + splits_df["Walker Election Day Votes"]
    splits_df["dem_nov_eday_share"] = splits_df["Warnock Election Day Votes"] / splits_df["nov_eday_votes"]
    splits_df["election_day_vote_rate"] = splits_df["nov_eday_votes"] / (splits_df["nov_vbm_votes"] + splits_df["nov_adv_votes"])

    # November Early Vote share
    # splits_df["total_dem_nov_early_share"] = (splits_df["Warnock Absentee by Mail Votes"] + splits_df["Warnock Advance Voting Votes"]) / (splits_df["nov_adv_votes"] + splits_df["nov_vbm_votes"])
    # splits_df["total_dem_nov_share"] = (splits_df["Warnock Absentee by Mail Votes"] + splits_df["Warnock Advance Voting Votes"] + splits_df["Warnock Election Day Votes"]) / (splits_df["nov_adv_votes"] + splits_df["nov_vbm_votes"] + splits_df["nov_eday_votes"])
    # splits_df["nov_early_votes"] = splits_df["nov_adv_votes"] + splits_df["nov_vbm_votes"]
    # splits_df["early_dem_nov_votes"] = (splits_df["nov_vbm_votes"] * splits_df["nov_early_votes"])
    # splits_df["nov_total_votes"] = splits_df["nov_early_votes"] + splits_df["nov_eday_votes"]
    ##### End November Early Voting Data Computation #####

    #### Current County Rate Calculations #####

    county_df = county_votes_cast_split.merge(splits_df, how="inner")
    county_df = county_df.merge(precinct_df, how="inner")

    # VBM
    vbm_total = county_df[county_df["Ballot Style"] == "MAILED"]

    vbm_df = vbm_total
    vbm_df["total_vbm_votes"] = vbm_total["isValid"]
    vbm_df["dem_vbm_votes"] = 0.
    vbm_df["dem_unadjusted_vbm_votes"] = vbm_df["dem_nov_vbm_share"] * vbm_df["total_vbm_votes"]
    vbm_df["gop_unadjusted_vbm_votes"] = vbm_df["total_vbm_votes"] - vbm_df["dem_unadjusted_vbm_votes"]

    for race in adv_scale_constants.keys():
        if race == 'white':
            adj = 1.08
        else:
            adj = 1.0
        vbm_df["dem_vbm_votes"] += adj * vbm_df[race + '_mail_turnout_share'] * vbm_df[race + '_mail_support_share'] * vbm_df["total_vbm_votes"]

    vbm_df["dem_vbm_share"] = vbm_df["dem_vbm_votes"] / vbm_df["total_vbm_votes"]
    vbm_df["gop_vbm_votes"] = vbm_df["total_vbm_votes"] - vbm_df["dem_vbm_votes"]

    # Early In Person Voting
    adv_total = county_df[county_df["Ballot Style"] == "IN PERSON"]
    adv_df = adv_total
    adv_df["total_adv_votes"] = adv_total["isValid"]
    adv_df["dem_adv_votes"] = 0.
    adv_df["dem_unadjusted_adv_votes"] = adv_df["dem_nov_adv_share"] * adv_df["total_adv_votes"]
    adv_df["gop_unadjusted_adv_votes"] = adv_df["total_adv_votes"] - adv_df["dem_unadjusted_adv_votes"]
    for race in adv_scale_constants.keys():
        if race == 'white':
            adj = 1.0
        else:
            adj = 1.0
        adv_df["dem_adv_votes"] += adj * adv_df[race + '_adv_turnout_share'] * adv_df[race + '_adv_support_share'] * adv_df["total_adv_votes"]
    adv_df["dem_adv_share"] = adv_df["dem_adv_votes"] / adv_df["total_adv_votes"]
    adv_df["gop_adv_votes"] = adv_df["total_adv_votes"] - adv_df["dem_adv_votes"]

    total_per_precinct = county_votes_cast_split.groupby(["County", "County Precinct"], as_index=False).sum().rename(columns={'isValid': 'total_votes_cast'})
    ev_total = county_df.merge(total_per_precinct, how="inner")

    # DO NOT DELETE THIS it is a dumb hack to remove duplicates, now that we've computed all we needed to anyways for splits by voting method and have duplicate rows for total # of votes cast.
    ev_total = ev_total[ev_total["Ballot Style"] == "IN PERSON"]

    # which columns do we keep for later calculations?
    cols_to_keep = ["County", "County Precinct"]
    cols_to_keep += ["dem_nov_eday_share", "election_day_vote_rate", "nov_vbm_votes", "nov_adv_votes"]    
    # cols_to_keep += ["dem_nov_eday_share", "election_day_vote_rate", "total_dem_nov_early_share", "total_dem_nov_share", "nov_early_votes", "nov_total_votes", "nov_vbm_votes", "nov_adv_votes"]
    cols_to_keep += ["total_votes_cast"]

    # for debugging/comparison; what was the november lead?
    cols_to_keep += ["dem_nov_vbm_margin", "dem_nov_adv_margin", "dem_nov_total_ev_margin"]

    ev_df = ev_total[cols_to_keep]
    ev_df["turnout_rate"] = ev_df["total_votes_cast"] / (ev_df["nov_vbm_votes"] + ev_df["nov_adv_votes"])
    ev_df["proj_eday_votes"] = ev_df["election_day_vote_rate"] * ev_df["total_votes_cast"] * eday_modifier
    ev_df["dem_eday_votes"] = ev_df["dem_nov_eday_share"] * ev_df["proj_eday_votes"]
    ev_df["gop_eday_votes"] = ev_df["proj_eday_votes"] - ev_df["dem_eday_votes"]

    county_result_df = vbm_df.merge(adv_df, left_on=["County", "County Precinct"], right_on=["County", "County Precinct"])
    county_result_df = county_result_df.merge(ev_df, left_on=["County", "County Precinct"], right_on=["County", "County Precinct"])

    # Total Votes
    county_result_df["Dem Total Votes"] = county_result_df["dem_eday_votes"] + county_result_df["dem_adv_votes"] + county_result_df["dem_vbm_votes"]
    county_result_df["GOP Total Votes"] = county_result_df["gop_eday_votes"] + county_result_df["gop_adv_votes"] + county_result_df["gop_vbm_votes"]

    if results_df is None:
        results_df = county_result_df
    else:
        results_df = pd.concat([results_df, county_result_df], ignore_index=True)
    print(f'{county_name} done!')

## HERE IS WHERE WE DO ALL THE REPORTING OF THE DATA

## REPORT THE MARGINS IN THE TERMINALx
# early_share_statewide = results_df["nov_early_votes"] / results_df.sum()["nov_early_votes"]

dem_votes = results_df["Dem Total Votes"].sum()
gop_votes = results_df["GOP Total Votes"].sum()

dem_vbm_share = results_df["dem_vbm_votes"].sum()/(results_df["dem_vbm_votes"].sum() + results_df["gop_vbm_votes"].sum())
gop_vbm_share = results_df["gop_vbm_votes"].sum()/(results_df["dem_vbm_votes"].sum() + results_df["gop_vbm_votes"].sum())

print("-------------------")
print("Dem VBM Share: ", round(dem_vbm_share * 100, 2))
print("GOP VBM Share: ", round(gop_vbm_share * 100, 2))
print("Dem VBM Votes: ", round(results_df["dem_vbm_votes"].sum(), 0))
print("GOP VBM Votes: ", round(results_df["gop_vbm_votes"].sum(), 0))
print("Total VBM Votes: ", round(results_df["gop_vbm_votes"].sum() + results_df["dem_vbm_votes"].sum(), 0))
print("-------------------\n")

dem_adv_share = results_df["dem_adv_votes"].sum()/(results_df["dem_adv_votes"].sum() + results_df["gop_adv_votes"].sum())
gop_adv_share = results_df["gop_adv_votes"].sum()/(results_df["dem_adv_votes"].sum() + results_df["gop_adv_votes"].sum())

print("-------------------")
print("Dem ADV Share: ", round(dem_adv_share * 100, 2))
print("GOP ADV Share: ", round(gop_adv_share * 100, 2))
print("Dem ADV Votes: ", round(results_df["dem_adv_votes"].sum(), 0))
print("GOP ADV Votes: ", round(results_df["gop_adv_votes"].sum(), 0))
print("Total ADV Votes: ", round(results_df["gop_adv_votes"].sum() + results_df["dem_adv_votes"].sum(), 0))
print("-------------------\n")

total_early_votes = results_df["dem_vbm_votes"].sum() + results_df["gop_vbm_votes"].sum() + results_df["dem_adv_votes"].sum() + results_df["gop_adv_votes"].sum()
dem_early_votes = results_df["dem_vbm_votes"].sum() + results_df["dem_adv_votes"].sum()
gop_early_votes = results_df["gop_vbm_votes"].sum() + results_df["gop_adv_votes"].sum()
dem_early_share = dem_early_votes/total_early_votes
gop_early_share = gop_early_votes/total_early_votes

print("-------------------")
print("Dem Total Early Share:", round(dem_early_share * 100, 2))
print("GOP Total Early Share:", round(gop_early_share * 100, 2))
print("Dem Total Early Votes", round(dem_early_votes, 0))
print("GOP Total Early Votes", round(gop_early_votes, 0))
print("Total Early Votes: ", round(total_early_votes, 0))
print("-------------------\n")

total_eday_votes = results_df["dem_eday_votes"].sum() + results_df["gop_eday_votes"].sum()
dem_eday_share = results_df["dem_eday_votes"].sum()/total_eday_votes
gop_eday_share = results_df["gop_eday_votes"].sum()/total_eday_votes

print("-------------------")
print("Dem Election Day Share: ", round(dem_eday_share * 100, 2))
print("GOP Election Day Share: ", round(gop_eday_share * 100, 2))
print("Dem Election Day Votes: ", round(results_df["dem_eday_votes"].sum(), 0))
print("GOP Election Day Votes: ", round(results_df["gop_eday_votes"].sum(), 0))
print("Total Election Day Votes: ", round(results_df["dem_eday_votes"].sum() + results_df["gop_eday_votes"].sum(), 0))
print("-------------------\n")

dem_total_share = dem_votes/(dem_votes + gop_votes)
gop_total_share = gop_votes/(dem_votes + gop_votes)

print("FORECAST")
print("-------------------")
print("DEM Share", round(dem_total_share * 100, 2))
print("GOP Share", round(gop_total_share * 100, 2))
print("DEM VOTES", round(dem_votes, 0))
print("GOP VOTES", round(gop_votes, 0))
print("TOTAL VOTES: ", round(dem_votes + gop_votes, 0))
margin = round((dem_total_share - gop_total_share) * 100, 2)
winner = "DEM" if margin > 0 else "GOP"
print("MARGIN: " + winner + " +" + str(abs(margin)))
print("-------------------\n")

## OUTPUT THE RESULTS TO A CSV

agg_dict = {'dem_vbm_votes': 'sum', 'gop_vbm_votes': 'sum', 'dem_adv_votes': 'sum', 'gop_adv_votes': 'sum', 'dem_eday_votes': 'sum', 'gop_eday_votes': 'sum'}
results_by_county = results_df.groupby(["County"]).agg(agg_dict)
results_by_county["Democratic Votes"] = results_by_county['dem_vbm_votes'] + results_by_county['dem_adv_votes'] + results_by_county['dem_eday_votes']
results_by_county["Republican Votes"] = results_by_county['gop_vbm_votes'] + results_by_county['gop_adv_votes'] + results_by_county['gop_eday_votes']
results_by_county["Democratic Share"] = 100 * results_by_county["Democratic Votes"]/(results_by_county["Democratic Votes"] + results_by_county["Republican Votes"])
results_by_county["Republican Share"] = 100 * results_by_county["Republican Votes"]/(results_by_county["Democratic Votes"] + results_by_county["Republican Votes"])
results_by_county["Democratic Share"] = results_by_county["Democratic Share"].round(2)
results_by_county["Republican Share"] = results_by_county["Republican Share"].round(2)

results_by_county["dem_vbm_votes"] = results_by_county["dem_vbm_votes"].round(0)
results_by_county["dem_adv_votes"] = results_by_county["dem_adv_votes"].round(0)
results_by_county["dem_eday_votes"] = results_by_county["dem_eday_votes"].round(0)
results_by_county["Democratic Votes"] = results_by_county["Democratic Votes"].round(0)

results_by_county["gop_vbm_votes"] = results_by_county["gop_vbm_votes"].round(0)
results_by_county["gop_adv_votes"] = results_by_county["gop_adv_votes"].round(0)
results_by_county["gop_eday_votes"] = results_by_county["gop_eday_votes"].round(0)
results_by_county["Republican Votes"] = results_by_county["Republican Votes"].round(0)

results_by_county["Total Votes"] = results_by_county["Republican Votes"] + results_by_county["Democratic Votes"]

results_by_county.to_csv("county_projections.csv")