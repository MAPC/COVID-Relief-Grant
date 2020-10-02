# -*- coding: utf-8 -*-
"""
Created on Tue Sep 15 11:42:19 2020

@author: cspence
"""

import numpy as np
import pandas as pd


''' Assemble data sources '''
gatewaycities = ['Attleboro', 'Barnstable', 'Brockton', 'Chelsea', 'Chicopee', 
                 'Everett', 'Fall River', 'Fitchburg', 'Haverhill', 'Holyoke',
                 'Lawrence', 'Leominster', 'Lowell', 'Lynn', 'Malden', 
                 'Methuen', 'New Bedford', 'Peabody', 'Pittsfield', 'Quincy',
                 'Revere', 'Salem', 'Springfield', 'Taunton', 'Westfield', 'Worcester']

# Import data on household income by household type by municipality, ACS 2014-2018
# Data available at https://datacommon.mapc.org/browser/datasets/338 as csv
hhincmuni_file = "Insert File Path Here"
hhinc = pd.read_csv(hhincmuni_file, low_memory=False)
# sum 'ami5080', 'ami3050', 'amiu30'

# Import data on language spoken at home with ability to speak English by municipality (ACS 2014-2018)
# Data available at https://datacommon.mapc.org/browser/datasets/240 as csv
englishabilitymuni_file = "Insert File Path Here"
englishtable = pd.read_csv(englishabilitymuni_file, low_memory=False)

# Import data on labor force by municipality, ACS 2014-2018
# Data available at https://datacommon.mapc.org/browser/datasets/129 as csv
laborforcemuni_file = "Insert File Path Here"
laborforce = pd.read_excel(laborforcemuni_file, sheet_name='Data')
# use "lf" or total labor force (est)

# Import population in poverty by municipality (ACS 2014-2018)
popinpovmuni_file = "Insert File Path Here"
# Data from https://datacommon.mapc.org/browser/datasets/57 as csv
poverty = pd.read_excel(popinpovmuni_file, sheet_name='Data')
# Use "inpov", "municipal"

unempmuni_file = "Insert File Path Here"
# Data from https://lmi.dua.eol.mass.gov/LMI/ClaimsData#
unemp= pd.read_excel(unempmuni_file, sheet_name='contclaims_raw')
# Fix names to match spelling in other sources
unemp['Area_Name'] = unemp['Area_Name'].replace(to_replace = ['Attleborough', 'Manchester-by-the-Sea', 'Nantucket, County'], value=['Attleboro', 'Manchester', 'Nantucket'])
# Used "Claims" column with "Week Ending Date" == 8/29/2020

# Import housing assistance needed data
# Data from https://www.mapc.org/planning101/covid-housing-gap-update-august/
housingassistancemuni_file = "Insert File Path Here"
housingassistance= pd.read_excel(housingassistancemuni_file, sheet_name='Assistance_Estimates_AllHHds')
# Use "total_Cost_assistance_none" field

# Weekly COVID-19 cases by muni
# Data from https://www.mass.gov/info-details/covid-19-response-reporting, 
case11file = "Insert file path here"
case11 = pd.read_excel(case11file, sheet_name='City_town')

# Read in Census 2018 population estimates.
# Data available at https://datacommon.mapc.org/browser/datasets/316 as csv.
census18popestfile = "Insert file path here"
munipopest = pd.read_excel(census18popestfile, sheet_name = 'Data')

# Read in sheet with municipality names as rows, community foundations as columns,
# entries = 0 where municipality row not served by community foundation column
# through grant; entry = 1 otherwise.
commfoundsfile = "Insert file path here"
comfounds = pd.read_excel(commfoundsfile, sheet_name = 'Sheet2')

# Create a list of names
cfs = comfounds.columns
cfs = cfs[4:]

# Create a function to max-min normalize a set of values. We will use this later.
def maxminnorm(series, scale):
    sermin = np.min(series.values)
    sermax = np.max(series.values)
    serrange = sermax - sermin
    normedser = ((series - sermin).divide(serrange)).multiply(float(scale))
    return(normedser)

''' Derive scoring statistics. Eliminate unnecessary columns. '''

# 1. Population in poverty
poverty = poverty.loc[poverty['muni_id'] <= 351]
poverty['inpov_score'] = maxminnorm(poverty['inpov'], 20.0)
poverty = poverty[['municipal', 'muni_id', 'inpov', 'inpov_score']]

# 2. Pandemic relief funds: Nothing here, this will be a "narrative."

# 3. Pandemic-related public health impact: 
#    Calculate total cases/100,000 since January 2020.
covidpoptable = munipopest.join(case11.set_index('City/Town'), on = 'municipal', lsuffix = 'census', rsuffix = 'covid')
covidpoptable['Total case count'] = covidpoptable['Total case count'].replace(to_replace="<5", value = float(2.5))
covidpoptable['Cases per 100k (est)'] = (covidpoptable['Total case count'].divide(covidpoptable['pop_est'])).multiply(float(100000))
covidpoptable = covidpoptable[['municipal', 'Total case count', 'pop_est', 'Cases per 100k (est)']]
covidpoptable = covidpoptable.dropna()
covidpoptable['Case Rate (score)'] = maxminnorm(covidpoptable['Cases per 100k (est)'], 20.0)


# 4. Population with unmet economic need

# a. Share of workers unemployed.
unemp = unemp.loc[unemp['Week Ending Date'] == np.datetime64('2020-08-29T00:00:00.000000000')]
unemp = unemp.join(laborforce.set_index('municipal'), on = 'Area_Name')
unemp['Claims'] = unemp['Claims'].replace(to_replace = ['*'], value = [float(0)])
unemp['claimsperworker'] = unemp['Claims'].divide(unemp['lf'])
unemp = unemp[['Area_Name', 'Claims', 'lf', 'claimsperworker']]
unemp['claimsperworker'] = unemp['claimsperworker'].replace(to_replace=[np.nan], value = [float(0)])
unemp['unemp_score'] = maxminnorm(unemp['claimsperworker'], 20.0)

# b. Total housing assistance need.
housingassistance['housinghelp_score'] = maxminnorm(housingassistance['total_Cost_assistance_none'], 20.0)
housingassistance = housingassistance[['muni', 'total_Cost_assistance_none', 'housinghelp_score']]
housingassistance['municipal'] = housingassistance['muni'].str.upper().str.title()
housingassistance = housingassistance[['municipal', 'total_Cost_assistance_none', 'housinghelp_score']]


# 5. Gateway city OR limited English pop above average OR low-income (80% ami) households above average:
    # Create a boolean column for each.
#a. Low-income households.
hhinc['lowinchhs'] = hhinc['ami5080'] + hhinc['ami3050'] + hhinc['amiu30']
hhinc['lowinchhsp'] = hhinc['ami5080p'] + hhinc['ami3050p'] + hhinc['amiu30p']
# Set boolean low income score to 1 if municipal low income percentage is higher than state percentage.
hhinc['lowinc_bool'] = 0.0
hhinc_ma = hhinc.loc[hhinc['municipal'] == 'Massachusetts']
ma_lowincp = hhinc_ma['lowinchhsp'].values[0]
hhinc['lowinc_bool'].loc[hhinc['lowinchhsp'] > ma_lowincp] = 1.0
# Remove regional tallies (not at municipal scale)
hhinc = hhinc.loc[hhinc['muni_id'] <= 351]
hhinc = hhinc[['municipal', 'lowinchhs', 'lowinchhsp', 'lowinc_bool']]

#b. Gateway cities: Create a gateway boolean column in hhinc.
hhinc['Gateway_bool'] = 0.0
hhinc['Gateway_bool'].loc[hhinc['municipal'].isin(gatewaycities)] = 1.0

#c. English limited
# englishtable = englishtable.loc[englishtable['muni_id'] <= 351]
englishtable['English-limited'] = englishtable['en_nw'] + englishtable['en_na']
englishtable['English-limited p'] = englishtable['en_nw_p'] + englishtable['en_na_p']
english_ma = englishtable.loc[englishtable['municipal'] == 'Massachusetts']
ma_englishlimp = english_ma['English-limited p'].values[0]
englishtable['english_bool'] = 0.0
englishtable['english_bool'].loc[englishtable['English-limited p'] > ma_englishlimp] = 1.0
# Remove regional tallies (not at municipal scale)
englishtable = englishtable.loc[englishtable['muni_id'] <= 351]
englishtable = englishtable[['municipal', 'English-limited', 'English-limited p', 'english_bool']]


''' Combine tables into one. '''
munitable = poverty.join(covidpoptable.set_index('municipal'), on = 'municipal')
munitable = munitable.join(unemp.set_index('Area_Name'), on = 'municipal')
munitable = munitable.join(housingassistance.set_index('municipal'), on = 'municipal')
munitable = munitable.join(hhinc.set_index('municipal'), on = 'municipal')
munitable = munitable.join(englishtable.set_index('municipal'), on = 'municipal')
# Set missing values (nan) to 0
munitable['housinghelp_score'] = munitable['housinghelp_score'].replace(to_replace =[np.nan], value = [float(0)])
munitable['total_Cost_assistance_none'] = munitable['total_Cost_assistance_none'].replace(to_replace =[np.nan], value = [float(0)])

''' Begin aggregating sub-scores to main scores'''
# Aggregate to form Econ Need Score
munitable['Econ Need Score'] = munitable['unemp_score'] + munitable['housinghelp_score']
munitable['Econ Need Score'] = maxminnorm(munitable['Econ Need Score'], 20.0)

# Aggregate "Gateway Plus" boolean columns to a boolean indicator: 1 if any of the criteria were met.
munitable['Gateway Ind'] = munitable['Gateway_bool'] + munitable['lowinc_bool'] + munitable['english_bool']
munitable['Gateway Ind'].loc[munitable['Gateway Ind'] > 1.0] = 1.0
# If meeting at least one "Gateway Plus" criterion, multiply by estimated population.
munitable['Gateway Pop'] = munitable['Gateway Ind'].multiply(munitable['pop_est'])

# Create a function to sum community foundation-wide metrics.
def evaluate_cf(cfname, commfounds, munitable):
    munis = commfounds.loc[commfounds[cfname] == 1]
    munis = munis['municipal'].values
    munirows = munitable.loc[munitable['municipal'].isin(munis)]
    servedmunis = munirows['municipal'].values.tolist()
    
    #1. Poverty: Count individuals in poverty across municipalities served
    inpov = sum(munirows['inpov'].values)
    
    #3. Health: Count total number of cases per person since January 2020 in 
    #   municipalities served.
    caserate = sum(munirows['Total case count'].values)/sum(munirows['pop_est'].values)
    
    #4. Economic impact: 
        # a. Total number of claims in municipalities served divided by total labor force in munis served.
    unemprate = sum(munirows['Claims'].values)/sum(munirows['lf'].values)
    housingneed = sum(munirows['total_Cost_assistance_none'].values)
    
    #5. Gateway Plus
    gateway = sum(munirows['Gateway Pop'].values)
    
    return([inpov, caserate, unemprate, housingneed, gateway, servedmunis])

# Create empty lists in which to store community foundation metrics.
cfname = list()
inpov = list()
caserate = list()
unemprate = list()
housingneed = list()
gateway = list()
servedmunis = list()
# Run through community foundations, calculate metrics.
for k in range(len(cfs)):
    cf = cfs[k]
    critvals = evaluate_cf(cf, comfounds, munitable)
    cfname.append(cf)
    inpov.append(critvals[0])
    caserate.append(critvals[1])
    unemprate.append(critvals[2])
    housingneed.append(critvals[3])
    gateway.append(critvals[4])
    servedmunis.append(critvals[5])
    
# Turn filled-in lists into a Dictionary, then dataframe.
cfsubcritdict = {'Community Foundation': cfname,
                 'In Poverty': inpov,
                 'Case Rate': caserate,
                 'Unemployment Rate': unemprate,
                 'Housing Gap': housingneed,
                 'Gateway Plus Population': gateway,
                 'Municipalities Served': servedmunis}
cfsubcrit = pd.DataFrame(data = cfsubcritdict)

''' Calculate main category scores. '''
cfsubcrit['Poverty Score'] = maxminnorm(cfsubcrit['In Poverty'], 20.0)

cfsubcrit['Health Impact Score'] = maxminnorm(cfsubcrit['Case Rate'], 20.0)

cfsubcrit['Unemp Score'] = maxminnorm(cfsubcrit['Unemployment Rate'], 20.0)
cfsubcrit['Housing Gap Score'] = maxminnorm(cfsubcrit['Housing Gap'], 20.0)
cfsubcrit['Economic Impact Sum'] = cfsubcrit['Unemp Score'] + cfsubcrit['Housing Gap Score']
cfsubcrit['Economic Impact Score'] = maxminnorm(cfsubcrit['Economic Impact Sum'], 20.0)

cfsubcrit['Gateway Plus Score'] = maxminnorm(cfsubcrit['Gateway Plus Population'], 20.0)
cfsubcrit['Final Score'] = cfsubcrit['Poverty Score'] + cfsubcrit['Health Impact Score'] + cfsubcrit['Economic Impact Score'] + cfsubcrit['Gateway Plus Score']

cfcrit = cfsubcrit[['Community Foundation', 'Poverty Score', 'Health Impact Score', 'Economic Impact Score', 'Gateway Plus Score', 'Final Score', 'Municipalities Served']]
destfile = "K:\\DataServices\\Projects\\Data_Requests\\2020\\DHCD_COVID_Grants\\Data\\Tabular\\CFresults.csv"
cfcrit.to_csv(destfile)

