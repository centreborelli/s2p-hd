
echo "do not run this file"

# NOTE: this is not a script because it requires a few hand-processed parts
# this is just for documentation in case I have to do this again
set -e
false
exit


# download pdf data sheet
wget https://dg-cms-uploads-production.s3.amazonaws.com/uploads/document/file/207/Radiometric_Use_of_WorldView-3_v2.pdf -O x.pdf


# extract individual pages to txt (first 20 pages suffice for visible spectrum)
for i in {1..20}; do
	pdftotext -f $i -l $i x.pdf page_$i.txt
done

# check that all pages are more or less consistent
wc -l page_*.txt
# oops, page 13 has two badly joined columns
vim page_13.txt # separate the bad columns


# for each page, separate each "paragraph" into different files
for i in {2..20}; do
	awk -v RS= "{print > (\"whatever-${i}-\" NR \".txt\")}" page_$i.txt
done

# paste the paragraphs of each page into columns
for i in {2..20}; do
	paste -d' ' whateer-${i}-{1..17}.txt > out_$i.txt
done

# the first page is irremediably different, we paste it by hand
cp page_1.txt out_1.txt
vim out_1.txt # paste the columns by hand

# concatenate into a single table
cat out_{1..20}.txt > t.txt

# visualize the result
echo 'plot for [col=2:11] "t.txt" using 0:col with lines' | gnuplot -persist
