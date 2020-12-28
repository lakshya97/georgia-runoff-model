import pandas as pd
import numpy as np
import warnings
from collections import Counter

warnings. simplefilter(action='ignore', category=Warning)

state_df = pd.read_csv("general_election_data.csv")
counties = sorted(state_df["County"].unique())
county_id = 0
results_df = None

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
    county_df = pd.read_csv(filename, sep=",", header=0)
    county_df = county_df[["Application Status", "Ballot Status", "Status Reason", "Ballot Return Date", "Ballot Style", "County Precinct"]]
    # Special case for Newton County
    if county_name == "Newton":
        for newton_id in range(1, 10):
            county_df = county_df.replace(to_replace={'County Precinct': str(newton_id)}, value={'County Precinct': '{:0>2}'.format(newton_id)})

    county_df["County Precinct"] = county_df["County Precinct"].astype(str)
    ## create a new column that says 1 if the ballot is validly cast, 0 if not
    county_df["isValid"] = county_df["Ballot Status"] == "A"
    county_df["Ballot Style"] = county_df["Ballot Style"].replace("ELECTRONIC", "MAILED")

    county_accept_totals = county_df.groupby(["County Precinct", "Ballot Style"]).size().reset_index(name='num_applications')

    ## create a count that sums up the valid votes cast and splits by style
    county_votes_cast_split = county_df.groupby(["County Precinct", "Ballot Style"], as_index=False).sum("isValid")
    county_votes_cast_totals = county_df[county_df["isValid"] == 1].groupby(["County Precinct"]).size().reset_index(name='total_votes')

    county_totals_and_rates = county_votes_cast_split.merge(county_accept_totals, left_on=["County Precinct", "Ballot Style"], right_on=["County Precinct", "Ballot Style"], how="inner")
    county_totals_and_rates["acceptance rate"] = county_totals_and_rates["isValid"]/county_totals_and_rates["num_applications"]

    # results_df = state_df[["County", "Precinct"]]
    county_df = state_df[state_df["County"] == county_name]

    # Early Voting Rate
    county_df["total_sen_adv_votes"] = county_df["Ossoff Advanced Voting Votes"] + county_df["Perdue Advanced Voting Votes"]
    county_df["total_pres_adv_votes"] = county_df["Biden Advanced Voting Votes"] + county_df["Trump Advanced Voting Votes"]
    county_df["average_total_adv_votes"] = (county_df["total_sen_adv_votes"] + county_df["total_pres_adv_votes"])/2
    county_df["dem_adv_average"] = (county_df["Biden Advanced Voting Votes"] + county_df["Ossoff Advanced Voting Votes"])/2
    county_df["dem_adv_share"] = county_df["dem_adv_average"]/county_df["average_total_adv_votes"]

    # Vote by Mail Rate
    county_df["total_sen_vbm_votes"] = county_df["Ossoff Absentee by Mail Votes"] + county_df["Perdue Absentee by Mail Votes"]
    county_df["total_pres_vbm_votes"] = county_df["Biden Absentee by Mail Votes"] + county_df["Trump Absentee by Mail Votes"]
    county_df["average_total_vbm_votes"] = (county_df["total_sen_vbm_votes"] + county_df["total_pres_vbm_votes"])/2
    county_df["dem_vbm_average"] = (county_df["Biden Absentee by Mail Votes"] + county_df["Ossoff Absentee by Mail Votes"])/2
    county_df["dem_vbm_share"] = county_df["dem_vbm_average"]/county_df["average_total_vbm_votes"]

    # Election Day Rate
    county_df["total_sen_eday_votes"] = county_df["Ossoff Election Day Votes"] + county_df["Perdue Election Day Votes"]
    county_df["total_pres_eday_votes"] = county_df["Biden Election Day Votes"] + county_df["Trump Election Day Votes"]
    county_df["average_total_eday_votes"] = (county_df["total_sen_eday_votes"] + county_df["total_pres_eday_votes"])/2
    county_df["dem_eday_average"] = (county_df["Biden Election Day Votes"] + county_df["Ossoff Election Day Votes"])/2
    county_df["dem_eday_share"] = county_df["dem_eday_average"]/county_df["average_total_eday_votes"]
    county_df["election_day_vote_rate"] = county_df["average_total_eday_votes"]/(county_df["average_total_adv_votes"] + county_df["average_total_vbm_votes"])

    precinct_lst_1 = sorted(county_df["Precinct"])
    precinct_lst_2 = sorted(county_totals_and_rates["County Precinct"])
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

    # this is just to avoid dumb duplicates, nothing else.
    ev_total = ev_total[ev_total["Ballot Style"] == "IN PERSON"]
    ev_df = ev_total[["County", "Precinct", "dem_eday_share"]]

    ev_df["proj_eday_votes"] = ev_total["election_day_vote_rate"] * ev_total["total_votes"]
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

dem_votes = results_df["Dem Total Votes"].sum()
gop_votes = results_df["GOP Total Votes"].sum()

state_df["tuple_set"] = "(" + state_df["County"] + "," + state_df["Precinct"] + ")"
results_df["tuple_set"] = "(" + results_df["County"] + "," + results_df["Precinct"] + ")"
output_counties = sorted(results_df["County"].unique())

print("DEM VOTES", dem_votes)
print("GOP VOTES", gop_votes)

print("Dem VBM Share: ", results_df["dem_vbm_votes"].sum()/(results_df["dem_vbm_votes"].sum() + results_df["gop_vbm_votes"].sum()))
print("GOP VBM Share: ", results_df["gop_vbm_votes"].sum()/(results_df["dem_vbm_votes"].sum() + results_df["gop_vbm_votes"].sum()))
print("Dem ADV Share: ", results_df["dem_adv_votes"].sum()/(results_df["dem_adv_votes"].sum() + results_df["gop_adv_votes"].sum()))
print("GOP ADV Share: ", results_df["gop_adv_votes"].sum()/(results_df["dem_adv_votes"].sum() + results_df["gop_adv_votes"].sum()))

total_early_votes = results_df["dem_vbm_votes"].sum() + results_df["gop_vbm_votes"].sum() + results_df["dem_adv_votes"].sum() + results_df["gop_adv_votes"].sum()

print("Dem Total Early share:", (results_df["dem_vbm_votes"].sum() + results_df["dem_adv_votes"].sum())/total_early_votes)
print("GOP Total Early share:", (results_df["gop_vbm_votes"].sum() + results_df["gop_adv_votes"].sum())/total_early_votes)
print("Dem Election Day Share: ", results_df["dem_eday_votes"].sum()/(results_df["dem_eday_votes"].sum() + results_df["gop_eday_votes"].sum()))
print("GOP Election Day Share: ", results_df["gop_eday_votes"].sum()/(results_df["dem_eday_votes"].sum() + results_df["gop_eday_votes"].sum()))
print("DEM Share", dem_votes/(dem_votes + gop_votes))
print("GOP Share", gop_votes/(dem_votes + gop_votes))

