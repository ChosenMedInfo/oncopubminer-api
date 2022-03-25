#!/bin/bash

# Create Output Dir!
OUTDIR=$2
if [ ! -d $OUTDIR ]; then
	mkdir -p $OUTDIR
fi

# Download Files!
ascp -T -l 200M -i ~/.aspera/connect/etc/asperaweb_id_dsa.openssh \
	--mode recv \
	--host ftp.ncbi.nlm.nih.gov \
	--user anonftp \
	--file-list $1 $OUTDIR/
