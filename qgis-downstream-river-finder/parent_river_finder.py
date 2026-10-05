from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsProject,
    QgsSpatialIndex,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsRectangle,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsField
)
from qgis.utils import iface
import math


# SETTINGS

layer = iface.activeLayer()

ID_FIELD = "River_Code"
NAME_FIELD = "River_Name"

OUT_NAME = "Down_Name"
OUT_CODE = "Down_Code"
OUT_COUNT = "DS_Count"
OUT_STATUS = "DS_Status"

# Topological tolerance in metres.
# Your snapping is already corrected, so keep this small.
TOLERANCE_M = 0.50

# Tolerance for identifying start/end of candidate segment
ALONG_TOLERANCE_M = 0.50


# VALIDATION

if layer is None:
    raise Exception("No active layer selected.")

if layer.geometryType() != 1:
    raise Exception("Active layer must be a line layer.")

field_names = [f.name() for f in layer.fields()]

if ID_FIELD not in field_names:
    raise Exception(f"Field '{ID_FIELD}' was not found.")

if NAME_FIELD not in field_names:
    raise Exception(f"Field '{NAME_FIELD}' was not found.")


# CHECK River_code UNIQUENESS

seen_ids = set()
duplicate_ids = set()

for f in layer.getFeatures():

    rid = f[ID_FIELD]

    if rid in seen_ids:
        duplicate_ids.add(rid)
    else:
        seen_ids.add(rid)

if duplicate_ids:

    example = list(duplicate_ids)[:20]

    raise Exception(
        "River_code is not unique.\n"
        f"Duplicate values include: {example}"
    )


# CREATE METRIC WORKING CRS
#
# Input is EPSG:4326, so calculate topology in metres.

extent = layer.extent()

center_lon = (
    extent.xMinimum() +
    extent.xMaximum()
) / 2.0

center_lat = (
    extent.yMinimum() +
    extent.yMaximum()
) / 2.0

utm_zone = int(
    math.floor((center_lon + 180.0) / 6.0) + 1
)

if center_lat >= 0:
    epsg = 32600 + utm_zone
else:
    epsg = 32700 + utm_zone

working_crs = QgsCoordinateReferenceSystem(
    f"EPSG:{epsg}"
)

print("------------------------------------------")
print("Working CRS:", working_crs.authid())
print("------------------------------------------")


transform = QgsCoordinateTransform(
    layer.crs(),
    working_crs,
    QgsProject.instance()
)


# FUNCTION:
# GET DOWNSTREAM ENDPOINT
# The line direction is assumed to already be:
# START = upstream
# END   = downstream
# For multipart features, we use the endpoint of the last
# non-empty part. This preserves the digitized direction when
# the multipart geometry contains ordered connected parts.


def get_downstream_point(geom):

    if geom.isMultipart():

        parts = geom.asMultiPolyline()

        # Find last valid part
        for part in reversed(parts):

            if part is not None and len(part) >= 2:

                p = part[-1]

                return QgsPointXY(
                    p.x(),
                    p.y()
                )

    else:

        line = geom.asPolyline()

        if line is not None and len(line) >= 2:

            p = line[-1]

            return QgsPointXY(
                p.x(),
                p.y()
            )

    return None


# PREPARE GEOMETRY CACHE

print("Preparing river geometries...")

projected_geometries = {}
downstream_points = {}
river_names = {}
river_codes = {}
line_lengths = {}

invalid_features = []

for feature in layer.getFeatures():

    fid = feature.id()

    geom = feature.geometry()

    if geom.isEmpty():

        invalid_features.append(fid)

        continue

    # Clone geometry so original layer is untouched
    g = QgsGeometry(geom)

    # Reproject geometry to metric CRS
    g.transform(transform)

    # Store geometry
    projected_geometries[fid] = g

    # Store attributes
    river_codes[fid] = str(
        feature[ID_FIELD]
    )

    if feature[NAME_FIELD] is None:
        river_names[fid] = ""
    else:
        river_names[fid] = str(
            feature[NAME_FIELD]
        )

    # Geometry length
    line_lengths[fid] = g.length()

    # Get downstream endpoint
    ds_point = get_downstream_point(g)

    if ds_point is None:

        invalid_features.append(fid)

        continue

    downstream_points[fid] = ds_point


print(
    "Valid river segments:",
    len(projected_geometries)
)

if invalid_features:

    print(
        "WARNING - invalid/empty features:",
        len(invalid_features)
    )


# BUILD SPATIAL INDEX

print("Building spatial index...")

spatial_index = QgsSpatialIndex()

for fid, geom in projected_geometries.items():

    temp = QgsFeature()

    temp.setId(fid)
    temp.setGeometry(geom)

    spatial_index.addFeature(temp)


# ADD OUTPUT FIELDS

existing_fields = [
    f.name()
    for f in layer.fields()
]

new_fields = []

if OUT_NAME not in existing_fields:

    new_fields.append(
        QgsField(
            OUT_NAME,
            QVariant.String,
            "string",
            254
        )
    )

if OUT_CODE not in existing_fields:

    new_fields.append(
        QgsField(
            OUT_CODE,
            QVariant.String,
            "string",
            254
        )
    )

if OUT_COUNT not in existing_fields:

    new_fields.append(
        QgsField(
            OUT_COUNT,
            QVariant.Int
        )
    )

if OUT_STATUS not in existing_fields:

    new_fields.append(
        QgsField(
            OUT_STATUS,
            QVariant.String,
            "string",
            100
        )
    )


if new_fields:

    layer.startEditing()

    for field in new_fields:
        layer.addAttribute(field)

    layer.updateFields()

    layer.commitChanges()


# FIELD INDEXES

idx_name = layer.fields().indexOf(OUT_NAME)
idx_code = layer.fields().indexOf(OUT_CODE)
idx_count = layer.fields().indexOf(OUT_COUNT)
idx_status = layer.fields().indexOf(OUT_STATUS)


# FIND IMMEDIATE DOWNSTREAM SEGMENTS

def find_downstream_candidates(current_fid):

    if current_fid not in downstream_points:

        return []

    downstream_point = downstream_points[
        current_fid
    ]

    point_geom = QgsGeometry.fromPointXY(
        downstream_point
    )

    
    # Spatial search
 

    search_rect = QgsRectangle(
        downstream_point.x() - TOLERANCE_M,
        downstream_point.y() - TOLERANCE_M,
        downstream_point.x() + TOLERANCE_M,
        downstream_point.y() + TOLERANCE_M
    )

    candidate_fids = spatial_index.intersects(
        search_rect
    )

    candidates = []

    
    # Examine candidate segments
    

    for candidate_fid in candidate_fids:

        # Never compare feature with itself
        if candidate_fid == current_fid:
            continue

        candidate_geom = projected_geometries.get(
            candidate_fid
        )

        if candidate_geom is None:
            continue

        candidate_length = line_lengths[
            candidate_fid
        ]

        if candidate_length <= 0:
            continue

       
        # Distance from current DS endpoint
        # to candidate river
        

        distance = candidate_geom.distance(
            point_geom
        )

        if distance > TOLERANCE_M:
            continue

       
        # Position of junction along candidate
       

        location = candidate_geom.lineLocatePoint(
            point_geom
        )

        if location < 0:
            continue

        
        # IMPORTANT:
        # If junction is at candidate END,
        # candidate is upstream
        # Therefore reject it.
       

        if location >= (
            candidate_length -
            ALONG_TOLERANCE_M
        ):

            continue

        
        # Candidate START
        # Candidate flows AWAY from junction
      

        if location <= ALONG_TOLERANCE_M:

            candidates.append(
                (
                    candidate_fid,
                    distance,
                    location,
                    "START"
                )
            )

        # Candidate INTERIOR
        # Tributary joins middle of candidate.
        # Because candidate direction is already
        # corrected, the part after the junction
        # is downstream.

        else:

            candidates.append(
                (
                    candidate_fid,
                    distance,
                    location,
                    "INTERIOR"
                )
            )

    return candidates


# PROCESS NETWORK

print("")
print("------------------------------------------")
print("Calculating immediate downstream rivers...")
print("------------------------------------------")

layer.startEditing()

total = len(projected_geometries)

found_count = 0
outlet_count = 0
multiple_count = 0
error_count = 0


for counter, feature in enumerate(
        layer.getFeatures(),
        start=1):

    fid = feature.id()

    if fid not in projected_geometries:

        continue

    current_code = river_codes[fid]

    candidates = find_downstream_candidates(
        fid
    )

    # NO DOWNSTREAM CANDIDATE
 

    if len(candidates) == 0:

        feature[idx_name] = None
        feature[idx_code] = None
        feature[idx_count] = 0
        feature[idx_status] = (
            "OUTLET / NO DOWNSTREAM"
        )

        layer.updateFeature(feature)

        outlet_count += 1


    # EXACTLY ONE DOWNSTREAM RIVER

    elif len(candidates) == 1:

        downstream_fid = candidates[0][0]
        connection_type = candidates[0][3]

        downstream_name = river_names[
            downstream_fid
        ]

        downstream_code = river_codes[
            downstream_fid
        ]

        feature[idx_name] = downstream_name
        feature[idx_code] = downstream_code
        feature[idx_count] = 1

        feature[idx_status] = (
            "OK - JOIN AT " +
            connection_type
        )

        layer.updateFeature(feature)

        found_count += 1


    # MULTIPLE DOWNSTREAM RIVERS
    #
    # This can represent a bifurcation/split.
    # We do NOT arbitrarily choose one.
    else:

        multiple_count += 1

        names = []
        codes = []

        for candidate in candidates:

            candidate_fid = candidate[0]

            name = river_names[
                candidate_fid
            ]

            code = river_codes[
                candidate_fid
            ]

            if name not in names:
                names.append(name)

            if code not in codes:
                codes.append(code)

        feature[idx_name] = (
            " | ".join(names)
        )

        feature[idx_code] = (
            " | ".join(codes)
        )

        feature[idx_count] = len(
            candidates
        )

        feature[idx_status] = (
            "MULTIPLE DOWNSTREAM"
        )

        layer.updateFeature(feature)


    # PROGRESS

    if counter % 500 == 0:

        print(
            f"Processed {counter:,} / "
            f"{total:,}"
        )


# SAVE EDITS

layer.commitChanges()

layer.triggerRepaint()


# FINAL REPORT

print("")
print("==========================================")
print("PROCESS COMPLETED")
print("==========================================")
print(
    f"Total segments       : {total:,}"
)
print(
    f"Downstream found     : {found_count:,}"
)
print(
    f"Outlets              : {outlet_count:,}"
)
print(
    f"Multiple downstream  : {multiple_count:,}"
)
print(
    f"Invalid geometries   : {len(invalid_features):,}"
)
print(
    f"Working CRS          : {working_crs.authid()}"
)
print(
    f"Tolerance             : {TOLERANCE_M} m"
)
print("==========================================")