import pandas as pd
import numpy as np
import warnings
import argparse
from collections import Counter

parser = argparse.ArgumentParser()
parser.add_argument('--mode', type=str, default="Biden", choices=["Biden", "Ossoff", "Average"])
args = parser.parse_args()

warnings.simplefilter(action='ignore', category=Warning)

state_df = pd.read_csv("general_election_data.csv")
counties = sorted(state_df["County"].unique())
county_id = 0
results_df = None
vbm_modifier = 1.0
adv_modifier = 1.0
eday_modifier = 1.0

def compute_list_difference(a, b):
    count = Counter(a) # count items in a
    count.subtract(b)  # subtract items that are in b
    diff = []
    for x in a:
        if count[x] > 0:
           count[x] -= 1
           diff.append(x)
    return diff

for county_name in counties:
    county_id += 1
    filename = 'Absentee Files/35211/' + '{:0>3}'.format(county_id) + '.csv'
    single_county_df = pd.read_csv(filename, sep=",", header=0)
    single_county_df = single_county_df[["Application Status", "Ballot Status", "Status Reason", "Ballot Return Date", "Ballot Style", "County Precinct"]]
    # Special case for Newton County
    if county_name == "Newton":
        for newton_id in range(1, 10):
            single_county_df = single_county_df.replace(to_replace={'County Precinct': str(newton_id)}, value={'County Precinct': '{:0>2}'.format(newton_id)})

    single_county_df["County Precinct"] = single_county_df["County Precinct"].astype(str)

    ## create a new column that says 1 if the ballot is validly cast, 0 if not
    single_county_df["isValid"] = 0
    single_county_df.loc[single_county_df["Ballot Status"] == "A", "isValid"] = 1

    single_county_df["Ballot Style"] = single_county_df["Ballot Style"].replace("ELECTRONIC", "MAILED")

    # adjust for how many vbm ballots are projected (default: no adjustment)
    single_county_df.loc[single_county_df["Ballot Style"] == "MAILED", "isValid"] *= vbm_modifier

    # adjust for how many in-person ballots are projected (default: no adjustment)
    single_county_df.loc[single_county_df["Ballot Style"] == "IN PERSON", "isValid"] *= adv_modifier

    county_accept_totals = single_county_df.groupby(["County Precinct", "Ballot Style"]).size().reset_index(name='num_applications')

    ## create a count that sums up the valid votes cast and splits by style
    county_votes_cast_split = single_county_df.groupby(["County Precinct", "Ballot Style"], as_index=False).sum("isValid")
    county_votes_cast_totals = single_county_df[single_county_df["isValid"] > 0].groupby(["County Precinct"]).sum().rename(columns={'isValid':'total_votes'})

    county_totals_and_rates = county_votes_cast_split.merge(county_accept_totals, left_on=["County Precinct", "Ballot Style"], right_on=["County Precinct", "Ballot Style"], how="inner")

    # I don't really use this, but it collects info on the VBM acceptance rate. Not really needed right now, though.
    # county_totals_and_rates["acceptance rate"] = county_totals_and_rates["isValid"]/county_totals_and_rates["num_applications"]

    county_df = state_df[state_df["County"] == county_name]

    # Early Voting Rate
    county_df["total_sen_adv_votes"] = county_df["Ossoff Advanced Voting Votes"] + county_df["Perdue Advanced Voting Votes"]
    county_df["total_pres_adv_votes"] = county_df["Biden Advanced Voting Votes"] + county_df["Trump Advanced Voting Votes"]
    if args.mode == "Average":
        county_df["average_total_adv_votes"] = (county_df["total_sen_adv_votes"] + county_df["total_pres_adv_votes"])/2
        county_df["dem_adv_average"] = (county_df["Biden Advanced Voting Votes"] + county_df["Ossoff Advanced Voting Votes"])/2
        county_df["dem_adv_share"] = county_df["dem_adv_average"]/county_df["average_total_adv_votes"]
    elif args.mode == "Biden":
        county_df["dem_adv_share"] = county_df["Biden Advanced Voting Votes"]/county_df["total_pres_adv_votes"]
    elif args.mode == "Ossoff":
        county_df["dem_adv_share"] = county_df["Ossoff Advanced Voting Votes"]/county_df["total_sen_adv_votes"]

    # Vote by Mail Rate
    county_df["total_sen_vbm_votes"] = county_df["Ossoff Absentee by Mail Votes"] + county_df["Perdue Absentee by Mail Votes"]
    county_df["total_pres_vbm_votes"] = county_df["Biden Absentee by Mail Votes"] + county_df["Trump Absentee by Mail Votes"]
    if args.mode == "Average":
        county_df["average_total_vbm_votes"] = (county_df["total_sen_vbm_votes"] + county_df["total_pres_vbm_votes"])/2
        county_df["dem_vbm_average"] = (county_df["Biden Absentee by Mail Votes"] + county_df["Ossoff Absentee by Mail Votes"])/2
        county_df["dem_vbm_share"] = county_df["dem_vbm_average"]/county_df["average_total_vbm_votes"]
    elif args.mode == "Biden":
        county_df["dem_vbm_share"] = county_df["Biden Absentee by Mail Votes"]/county_df["total_pres_vbm_votes"]
    elif args.mode == "Ossoff":
        county_df["dem_vbm_share"] = county_df["Ossoff Absentee by Mail Votes"]/county_df["total_sen_vbm_votes"]

    # Election Day Rate
    county_df["total_sen_eday_votes"] = county_df["Ossoff Election Day Votes"] + county_df["Perdue Election Day Votes"]
    county_df["total_pres_eday_votes"] = county_df["Biden Election Day Votes"] + county_df["Trump Election Day Votes"]
    if args.mode == "Average":
        county_df["average_total_eday_votes"] = (county_df["total_sen_eday_votes"] + county_df["total_pres_eday_votes"])/2
        county_df["dem_eday_average"] = (county_df["Biden Election Day Votes"] + county_df["Ossoff Election Day Votes"])/2
        county_df["dem_eday_share"] = county_df["dem_eday_average"]/county_df["average_total_eday_votes"]
        county_df["election_day_vote_rate"] = county_df["average_total_eday_votes"]/(county_df["average_total_adv_votes"] + county_df["average_total_vbm_votes"])
    elif args.mode == "Biden":
        county_df["dem_eday_share"] = county_df["Biden Election Day Votes"]/county_df["total_pres_eday_votes"]
        county_df["election_day_vote_rate"] = county_df["total_pres_eday_votes"]/(county_df["total_pres_vbm_votes"] + county_df["total_pres_adv_votes"])
    elif args.mode == "Ossoff":
        county_df["dem_eday_share"] = county_df["Ossoff Election Day Votes"]/county_df["total_sen_eday_votes"]
        county_df["election_day_vote_rate"] = county_df["total_sen_eday_votes"] /(county_df["total_sen_vbm_votes"] + county_df["total_sen_adv_votes"])

    # County Rate
    county_df = county_df.merge(county_totals_and_rates, left_on=["Precinct"], right_on=["County Precinct"], how="inner")

    # VBM
    vbm_total = county_df[county_df["Ballot Style"] == "MAILED"]
    vbm_df = vbm_total[["County", "Precinct", "dem_vbm_share"]]
    vbm_df["total_vbm_votes"] = vbm_total["isValid"]
    vbm_df["dem_vbm_votes"] = vbm_df["dem_vbm_share"] * vbm_df["total_vbm_votes"]
    vbm_df["gop_vbm_votes"] = vbm_df["total_vbm_votes"] - vbm_df["dem_vbm_votes"]
    
    # Advanced Voting 
    adv_total = county_df[county_df["Ballot Style"] == "IN PERSON"]
    adv_df = adv_total[["County", "Precinct", "dem_adv_share"]]
    adv_df["total_adv_votes"] = adv_total["isValid"]
    adv_df["dem_adv_votes"] = adv_df["dem_adv_share"] * adv_df["total_adv_votes"]
    adv_df["gop_adv_votes"] = adv_df["total_adv_votes"] - adv_df["dem_adv_votes"]

    # Election Day
    ev_total = county_df.merge(county_votes_cast_totals, left_on="Precinct", right_on=["County Precinct"], how="inner")

    # this is just to avoid dumb duplicates, nothing else. Otherwise, you have two rows with the same total vote data per precinct: Mailed and In Person. We don't need that.
    ev_total = ev_total[ev_total["Ballot Style"] == "IN PERSON"]
    ev_df = ev_total[["County", "Precinct", "dem_eday_share"]]

    ev_df["proj_eday_votes"] = ev_total["election_day_vote_rate"] * ev_total["total_votes"] * eday_modifier
    ev_df["dem_eday_votes"] = ev_df["dem_eday_share"] * ev_df["proj_eday_votes"]
    ev_df["gop_eday_votes"] = ev_df["proj_eday_votes"] - ev_df["dem_eday_votes"]

    county_result_df = vbm_df.merge(adv_df, left_on=["County", "Precinct"], right_on=["County", "Precinct"])
    county_result_df = county_result_df.merge(ev_df, left_on=["County", "Precinct"], right_on=["County", "Precinct"])

    # Total Votes
    county_result_df["Dem Total Votes"] = county_result_df["dem_eday_votes"] + county_result_df["dem_adv_votes"] + county_result_df["dem_vbm_votes"]
    county_result_df["GOP Total Votes"] = county_result_df["gop_eday_votes"] + county_result_df["gop_adv_votes"] + county_result_df["gop_vbm_votes"]
    if results_df is None:
        results_df = county_result_df
    else:
        results_df = pd.concat([results_df, county_result_df], ignore_index=True)


## HERE IS WHERE WE DO ALL THE REPORTING OF THE DATA

## REPORT THE MARGINS IN THE TERMINAL

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

results_by_county.to_csv("county_projections.csv")