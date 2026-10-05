# QGIS Downstream River Finder

A PyQGIS workflow for automatically identifying the immediate
downstream river segment in a direction-corrected river network.

## Overview

When working with a large river network, identifying the immediate
downstream segment manually can become repetitive and time-consuming.

This script automates the process by examining the downstream endpoint
of each river segment and identifying connected downstream candidates.

## What the script does

The workflow:

1. Validates the active QGIS layer.
2. Checks that `River_Id` values are unique.
3. Creates a metric working CRS.
4. Extracts the downstream endpoint of each river segment.
5. Builds a spatial index for efficient candidate searching.
6. Identifies connected downstream segments.
7. Handles downstream connections occurring at the start or interior
   of a candidate segment.
8. Identifies outlets where no downstream segment is found.
9. Reports cases with multiple downstream candidates.
10. Writes the results back to the active QGIS layer.

## Requirements

- QGIS 3.x
- PyQGIS
- A line-based river network

No additional Python packages are required.

## Input requirements

The active QGIS layer must:

- be a line layer
- contain a unique `River_Id` field
- contain a `River_Name` field
- have line direction representing:

```text
START = upstream
END   = downstream
```
## Output fields

The script creates the following fields:
| Field | Description |
| :--- | :--- |
|Down_Name|Immediate downstream river name|
|Down_Code|Immediate downstream river code|
|DS_Count|Number of downstream candidates|
|DS_Status|Status of downstream detection|

## Running the tool

1. Open QGIS.
1. Load the river-network layer.
1. Make the river layer the active layer.
1. Open the QGIS Python Console.
1. Run *parent_river_finder.py*
1. Open the attribute table and inspect the generated fields.

## Processing logic
```text
River network
      ↓
Validate input
      ↓
Check River_Code
      ↓
Create metric working CRS
      ↓
Extract downstream endpoints
      ↓
Build spatial index
      ↓
Find candidate segments
      ↓
Check connection position
      ↓
Identify downstream segment
      ↓
Write result to QGIS
```

## Important assumptions

The river network must already have the correct flow direction.

The script assumes:
```text
START → END
upstream → downstream
```
It does not automatically determine river direction from elevation.

## Multiple downstream segments

Where multiple downstream candidates are found, the script does not arbitrarily select one. Instead, the result is marked:

*MULTIPLE DOWNSTREAM*

This allows potentially complex network situations to be reviewed separately.

## Tolerance

The default spatial tolerance is:
*0.50 metres*
This can be adjusted in the settings section of the script.

## Author

Rajith K
