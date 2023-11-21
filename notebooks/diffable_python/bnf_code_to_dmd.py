# ---
# jupyter:
#   jupytext:
#     cell_metadata_filter: all
#     notebook_metadata_filter: all,-language_info
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.3.3
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# # Mapping BNF codes to dm+d

# We have had a request from NHS England:
#
# >Our initial need is to have a reference file that can be used to map data in BNF code form (from NHS BSA) to drug information in dm+d (SNOMED) form (at VMP/AMP level but also with VTM information).
#
# We hold this information in the BQ database, and should be able to create a query to deliver this need.

import os
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import matplotlib.ticker as ticker
import matplotlib.dates as mdates
import seaborn as sns
from matplotlib.dates import  DateFormatter
# %matplotlib inline
from ebmdatalab import bq
from ebmdatalab import charts
from ebmdatalab import maps
import datetime
import openpyxl

# ## Create data from BigQuery

sql = """
  SELECT
  "vmp" AS type, # create type column, shows whether VMP or AMP
  vmp.id AS id, # VMP code
  vmp.nm AS nm, # VMP name
  vmp.vtm AS vtm, # VTM code
  vtm.nm AS vtm_nm, # VTM name
  bnf_code, # BNF code
  vpidprev AS vmp_previous, # Previous VMP code
  vpiddt AS vmp_previous_date # Date that previous VMP code changed
FROM
  ebmdatalab.dmd.vmp_full AS vmp
LEFT OUTER JOIN
  dmd.vtm AS vtm
ON
  vmp.vtm = vtm.id

UNION ALL # join VMP and AMP tables together to form single table
SELECT
  "amp" AS type,
  amp.id,
  amp.descr,
  vmp.vtm,
  vtm.nm AS vtm_nm,
  amp.bnf_code AS bnf_code,
  NULL AS amp_previous,
  NULL AS amp_previous_date
FROM
  ebmdatalab.dmd.amp_full AS amp
INNER JOIN
  dmd.vmp AS vmp # join VMP to AMP table to get VMP codes to obtain VTM information
ON
  amp.vmp = vmp.id
LEFT OUTER JOIN
  dmd.vtm AS vtm 
ON
  vmp.vtm = vtm.id 
  """
exportfile = os.path.join("..","data","dmd_df.csv")
dmd_df = bq.cached_read(sql, csv_path=exportfile, use_cache=True)
exportfile2 = os.path.join("..","data","bnf_to_dmd.csv")
dmd_df['id'] = dmd_df['id'].astype('Int64')  # ensure csv is integer
dmd_df['vtm'] = dmd_df['vtm'].astype('Int64') # ensure csv is integer
dmd_df['vmp_previous'] = dmd_df['vmp_previous'].astype('Int64') # ensure csv is integer
exportfile2 = os.path.join("..","data","bnf_to_dmd.csv")
dmd_df.to_csv(exportfile2) # export integer version

dmd_df.head()

# As we can see from above we appear to have successfully imported all `VMPs` and `AMPs`.  However, there are some products which either do not have a `VTM` or `bnf_code`.  We will explore this further below.

# #### Check data with 12 months of primary care prescribing data

# Importing prescribing data from BigQuery to check the impact of "missing" data

# +
sql = """
SELECT
  bnf_code,
  bnf_name,
  SUM(items) AS items
FROM
  ebmdatalab.hscic.normalised_prescribing AS rx
WHERE
  month BETWEEN '2022-09-01'
  AND '2023-08-01'
GROUP BY
  bnf_name,
  bnf_code
  """

exportfile = os.path.join("..","data","rx_df.csv")
rx_df = bq.cached_read(sql, csv_path=exportfile, use_cache=True)
# -

rx_df.head()

# We can now merge the two dataframes on BNF code

test_df = pd.merge(dmd_df, rx_df, left_on='bnf_code', right_on='bnf_code', how='right')

test_df.head()

# We can now check by seeing which items prescribed which don't have a corresponding `dm+d` code

test_df_no_dmd = test_df[test_df['id'].isnull()].sort_values(by='items', ascending=False) # filter only prescribing which has a null VMP or AMP
test_df_no_dmd.head()

# We can see from the above there are very few items apart from "unspecified item", which by definition cannot have a BNF code.

# The other part of the request was to link `VTM` codes.  We can also check which drugs do not link to a `VTM`.

test_vtm_no_dmd  = test_df[test_df['vtm'].isnull()].sort_values(by='items', ascending=False)

test_vtm_no_dmd.head(30)

group_vtm_no_dmd = test_vtm_no_dmd.groupby(['bnf_name'])[['items']].mean().sort_values(by='items', ascending=False)

group_vtm_no_dmd.head(30)

# The largest number of prescribing items with a `NULL` `VTM` are either a) where they are not drugs, but appliances or devices (such as Freestyle Libre), OR where the drug has more than 3 ingredients.  In this case (such as Laxido) no VTM is assigned to the formulation in the dm+d.  Therefore it appears that the table accurately reflects what the dm+d says.



