# georgia-runoff-model
A model that computes runoff margins by projecting the November electorate split by precinct onto current totals.

To run this, create a subfolder called "Absentee Files", download the voter absentee file from https://elections.sos.ga.gov/Elections/voterabsenteefile.do, and move it into that subdirectory.

The precinct adjustment data was provided by Joe Gantt (twitter.com/joe__gantt)

After speaking with Nate Cohn of the New York Times, we have added an adjustment flag to account for race and party in the runoffs

The precinct adjustment (triggered by the --adjust flag) goes as follows: 

Take each racial group's early in-person turnout rate and multiply it by the racial group's distribution within each precinct. Take the percentage you get and multiply by the number of registered voters of that race in the precinct, then normalize that to the actual votes cast. This reweights your electorate. Do this process for November and for the runoff in January.

Now, to get the votes cast per party, use the following margins: 90-10 Black voters, 62-38 for Hispanic/AAPI/Other. Use the November votes cast to calculate your white vote share per precinct, then apply the margins you get to your January rescaled voter electorate to get the votes cast per party with race adjustment. Call this party_race_votes.

For party adjustment, we take the ratio of early votes that cast votes in the June primary and calculate the NPA skew per precinct (for example Dem_votes - dem_primary_voters = dem_npa_votes). Now, the data we see from Siena suggests Democrats are 1.16x more likely to be voting early in-person than the GOP, so apply that ratio to the Democratic primary voters per precinct and keep the NPA skew constant, and you will get the partisan breakdown of Janaury. Call this party_affiliation_votes. We weight this by half of the race votes to avoid for double-counting the affiliation spike that would naturally occur with partisan lean, but we can't ignore it entirely because Democratic white voters are also more likely to return their ballots.

Compute the index difference in percentage from November in margin for calculations with both the race adjustment (race_index) and 
the party adjustment (party_index)

Now, adjust the November Democratic margins by doing November_vote_margin + race_index + 0.5 * party_index 
(this is done to because race and party are somewhat intertwined, but you must account for both, so we give party 1/2 the weight of race)
