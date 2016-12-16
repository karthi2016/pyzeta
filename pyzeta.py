#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# file: pyzeta.py
# author: #cf
# version: 0.2.0


# =================================
# Import statements
# =================================

import os
import re
import csv
import glob
import pandas as pd
import numpy as np
from collections import Counter
import treetaggerwrapper
import pygal
from pygal import style
from scipy import stats


# import itertools
# import shutil
# from sklearn.decomposition import PCA

# =================================
# Shared functions
# =================================


def get_filename(file):
    filename, ext = os.path.basename(file).split(".")
    print(filename)
    return filename


def read_plaintext(file):
    with open(file, "r") as infile:
        text = infile.read()
        return text


def read_csvfile(filepath):
    with open(filepath, "r", newline="\n") as csvfile:
        content = csv.reader(csvfile, delimiter='\t')
        alllines = [line for line in content]
        return alllines


def save_dataframe(allfeaturecounts, currentfile):
    with open(currentfile, "w") as outfile:
        allfeaturecounts.to_csv(outfile, sep="\t")


# =================================
# Functions: prepare
# =================================


def run_treetagger(text, language):
    tagger = treetaggerwrapper.TreeTagger(TAGLANG=language)
    tagged = tagger.tag_text(text)
    return tagged


def save_tagged(taggedfolder, filename, tagged):
    taggedfilename = taggedfolder + "/" + filename + ".csv"
    with open(taggedfilename, "w") as outfile:
        writer = csv.writer(outfile, delimiter='\t')
        for item in tagged:
            item = re.split("\t", item)
            writer.writerow(item)


def prepare(plaintextfolder, language, taggedfolder):
    print("--prepare")
    if not os.path.exists(taggedfolder):
        os.makedirs(taggedfolder)
    for file in glob.glob(plaintextfolder + "*.txt"):
        filename = get_filename(file)
        text = read_plaintext(file)
        tagged = run_treetagger(text, language)
        save_tagged(taggedfolder, filename, tagged)
    print("Done.")


# =================================
# Functions: Zeta
# =================================


def make_filelist(metadatafile, contrast):
    """
    Based on the metadata, create two lists of files, each from one group.
    The category to check and the two labels are found in Contrast.
    """
    print("--make_filelist")
    with open(metadatafile, "r") as infile:
        metadata = pd.DataFrame.from_csv(infile, sep=";")
        # print(metadata.head())
        onemetadata = metadata[metadata[contrast[0]].isin([contrast[1]])]
        twometadata = metadata[metadata[contrast[0]].isin([contrast[2]])]
        onelist = list(onemetadata.loc[:, "idno"])
        twolist = list(twometadata.loc[:, "idno"])
        # print(onelist, twolist)
        print("----number of texts: " + str(len(onelist)) + " and " + str(len(twolist)))
        return onelist, twolist


def read_stoplistfile(stoplistfile):
    print("--read_stoplistfile")
    with open(stoplistfile, "r") as infile:
        stoplist = infile.read()
        stoplist = list(re.split("\n", stoplist))
        # print(stoplist)
        return stoplist


def select_features(segment, pos, forms, stoplist):
    """
    Selects the desired features (words, lemmas or pos) from the lists of texts.
    Turns the complete list into a set, then turns into a string for better saving.
    TODO: Add a replacement feature for words like "j'" or "-ils"
    """
    if pos != "all":
        if forms == "words":
            features = [line[0].lower() for line in segment if
                        len(line) == 3 and len(line[0]) > 2 and line[0] not in stoplist and pos in line[1]]
        if forms == "lemmata":
            features = [line[2].lower() for line in segment if
                        len(line) == 3 and len(line[0]) > 2 and line[0] not in stoplist and pos in line[1]]
        if forms == "pos":
            features = [line[1].lower() for line in segment if
                        len(line) == 3 and len(line[0]) > 2 and line[0] not in stoplist and pos in line[1]]
    elif pos == "all":
        if forms == "words":
            features = [line[0].lower() for line in segment if
                        len(line) == 3 and len(line[0]) > 2 and line[0] not in stoplist]
        if forms == "lemmata":
            features = [line[2].lower() for line in segment if
                        len(line) == 3 and len(line[0]) > 2 and line[0] not in stoplist]
        if forms == "pos":
            features = [line[1].lower() for line in segment if
                        len(line) == 3 and len(line[0]) > 2 and line[0] not in stoplist]
    else:
        features = []
    setfeatures = list(set(features))
    return setfeatures


def save_segment(features, segsfolder, segmentid):
    segmentfile = segsfolder + segmentid + ".txt"
    featuresjoined = " ".join(features)
    with open(segmentfile, "w") as outfile:
        outfile.write(featuresjoined)


def count_features(segment, segmentid):
    featurecount = Counter(segment)
    featurecount = dict(featurecount)
    featurecount = pd.Series(featurecount, name=segmentid)
    # print(featurecount)
    return featurecount


def make_segments(taggedfolder, currentlist, seglength,
                  segsfolder, pos, forms, stoplist, currentfile):
    """
    Calls a function to load each complete tagged text.
    Splits the whole text document into segments of fixed length; discards the rest.
    Calls a function to select the desired features from each segment.
    Calls a function to save each segment of selected features to disc.
    """
    print("--make_segments")
    allfeaturecounts = []
    for filename in currentlist:
        filepath = taggedfolder + filename + ".csv"
        if os.path.isfile(filepath):
            alllines = read_csvfile(filepath)
            numsegs = int(len(alllines) / seglength)
            for i in range(0, numsegs):
                segmentid = filename + "-" + "{:04d}".format(i)
                segment = alllines[i * seglength:(i + 1) * seglength]
                features = select_features(segment, pos, forms, stoplist)
                save_segment(features, segsfolder, segmentid)
                featurecount = count_features(features, segmentid)
                allfeaturecounts.append(featurecount)
    allfeaturecounts = pd.concat(allfeaturecounts, axis=1)
    allfeaturecounts = allfeaturecounts.fillna(0).astype(int)
    save_dataframe(allfeaturecounts, currentfile)
    # print(allfeaturecounts)
    return allfeaturecounts


def calculate_zetas(allfeaturecountsone, allfeaturecountstwo):
    """
    Perform the Zeta score calculation.
    Zeta = proportion of segments containing the type in group one minus proportion in group two
    """
    print("--calculate_zetas")
    # Calculate the proportions by dividing the row-wise sums by the number of segments
    allfeaturecountsone["docpropone"] = np.divide(np.sum(allfeaturecountsone, axis=1), len(allfeaturecountsone.columns))
    allfeaturecountstwo["docproptwo"] = np.divide(np.sum(allfeaturecountstwo, axis=1), len(allfeaturecountstwo.columns))
    zetascoredata = pd.concat([allfeaturecountsone.loc[:, "docpropone"], allfeaturecountstwo.loc[:, "docproptwo"]],
                              axis=1, join="outer")
    zetascoredata = zetascoredata.fillna(0)
    # The next line contains the actual zeta score calculation
    zetascoredata["zetascores"] = zetascoredata.loc[:, "docpropone"] - zetascoredata.loc[:, "docproptwo"]
    zetascoredata = zetascoredata.sort_values("zetascores", ascending=False)
    # print(zetascoredata.head(5))
    # print(zetascoredata.tail(5))
    return zetascoredata


def zeta(taggedfolder, metadatafile, contrast,
         datafolder, resultsfolder, seglength,
         pos, forms, stoplistfile):
    """
    Main coordinating function for "pyzeta.zeta"
    Python implementation of Craig's Zeta. 
    Status: proof-of-concept quality.
    """

    # Generate necessary file and folder names
    contraststring = contrast[1] + "-" + contrast[2]
    parameterstring = str(seglength) + "-" + forms + "-" + str(pos)
    segsfolder = datafolder + contraststring + "_" + parameterstring + "/"
    zetascorefile = resultsfolder + "zetascores_" + contraststring + "_" + parameterstring + ".csv"
    onefile = datafolder + "features_" + contrast[1] + "_" + parameterstring + ".csv"
    twofile = datafolder + "features_" + contrast[2] + "_" + parameterstring + ".csv"

    # Create necessary folders
    if not os.path.exists(datafolder):
        os.makedirs(datafolder)
    if not os.path.exists(segsfolder):
        os.makedirs(segsfolder)
    if not os.path.exists(resultsfolder):
        os.makedirs(resultsfolder)

    # Generate list of files for the two groups and get stoplist
    onelist, twolist = make_filelist(metadatafile, contrast)
    stoplist = read_stoplistfile(stoplistfile)

    # Create segments with selected types and turn into count matrix
    allfeaturecountsone = make_segments(taggedfolder, onelist, seglength, segsfolder, pos, forms, stoplist, onefile)
    allfeaturecountstwo = make_segments(taggedfolder, twolist, seglength, segsfolder, pos, forms, stoplist, twofile)

    # Perform the actual Zeta score calculation
    zetascoredata = calculate_zetas(allfeaturecountsone, allfeaturecountstwo)
    save_dataframe(zetascoredata, zetascorefile)


# =================================
# Functions: plot zetadata
# =================================

zeta_style = pygal.style.Style(
    background='white',
    plot_background='white',
    font_family="FreeSans",
    title_font_size=20,
    legend_font_size=16,
    label_font_size=12,
    opacity_hover=0.2)


def calculate_confint(zetadata):
    """
    Calculate the confidence interval for the zeta score distribution.
    Status: Not useful because a huge part of the scores are beyond the confint.
    """
    print("----calculate_confint")
    zetascores = list(zetadata.loc[:, "zetascores"])
    numvals = len(zetascores)
    mean = np.mean(zetascores)
    sem = stats.sem(zetascores)
    coveredint = 0.9995  # the area of the distribution to be excluded
    confint = stats.norm.interval(coveredint,
                                   loc=mean,
                                   scale=sem)
    # print(confint)
    return confint


def get_zetadata(zetascorefile, numwords):
    print("----get_zetadata")
    with open(zetascorefile, "r") as infile:
        zetadata = pd.DataFrame.from_csv(infile, sep="\t")
        # print(zetadata.head())
        zetadata.drop(["docpropone", "docproptwo"], axis=1, inplace=True)
        zetadata.sort_values("zetascores", ascending=False, inplace=True)
        confint = calculate_confint(zetadata)
        zetadatahead = zetadata.head(numwords)
        zetadatatail = zetadata.tail(numwords)
        zetadata = zetadatahead.append(zetadatatail)
        zetadata = zetadata.reset_index(drop=False)
        # print(zetadata.head())
        return zetadata, confint


def plot_zetadata(zetadata, contrast, contraststring, zetaplotfile, numwords):
    print("----plot_zetadata")
    plot = pygal.HorizontalBar(style = zeta_style,
                               print_values = False,
                               print_labels = True,
                               show_legend = False,
                               range = (-1, 1),
                               title = ("Kontrastive Analyse mit Zeta\n (" +
                                        str(contrast[2]) + " vs. " + str(contrast[1]) + ")"),
                               x_title = "Zeta-Score",
                               y_title = str(numwords) + " Worte pro Partition"
                               )
    for i in range(len(zetadata)):
        if zetadata.iloc[i, 1] > 0.8:
            color = "#00cc00"
        if zetadata.iloc[i, 1] > 0.7:
            color = "#14b814"
        if zetadata.iloc[i, 1] > 0.6:
            color = "#29a329"
        elif zetadata.iloc[i, 1] > 0.5:
            color = "#3d8f3d"
        elif zetadata.iloc[i, 1] > 0.3:
            color = "#4d804d"
        elif zetadata.iloc[i, 1] < -0.8:
            color = "#0066ff"
        elif zetadata.iloc[i, 1] < -0.7:
            color = "#196be6"
        elif zetadata.iloc[i, 1] < -0.6:
            color = "#3370cc"
        elif zetadata.iloc[i, 1] < -0.5:
            color = "#4d75b3"
        elif zetadata.iloc[i, 1] < -0.3:
            color = "#60799f"
        else:
            color = "#585858"
        plot.add(zetadata.iloc[i, 0], [{"value": zetadata.iloc[i, 1], "label": zetadata.iloc[i, 0], "color": color}])
    plot.render_to_file(zetaplotfile)


def plot_zetascores(numfeatures, contrast, contraststring, parameterstring, resultsfolder):
    print("--plot_zetascores")
    # Define some filenames
    zetascorefile = resultsfolder + "zetascores_" + contraststring + "_" + parameterstring + ".csv"
    zetaplotfile = resultsfolder + "scoresplot_" + contraststring + "_" + parameterstring + "-" + str(numfeatures) + ".svg"
    # Get the data and plot it
    zetadata, confint = get_zetadata(zetascorefile, numfeatures)
    plot_zetadata(zetadata, contrast, contraststring, zetaplotfile, numfeatures)


# ==============================================
# Scatterplot of types
# ==============================================


def get_scores(zetascorefile, numfeatures):
    print("----get_scores")
    with open(zetascorefile, "r") as infile:
        zetascores = pd.DataFrame.from_csv(infile, sep="\t")
        positivescores = zetascores.head(numfeatures)
        negativescores = zetascores.tail(numfeatures)
        scores = pd.concat([positivescores, negativescores])
        # print(scores.head())
        return scores


def make_data(scores):
    print("----make_data")
    thetypes = list(scores.index)
    propsone = list(scores.loc[:, "docpropone"])
    propstwo = list(scores.loc[:, "docproptwo"])
    zetas = list(scores.loc[:, "zetascores"])
    return thetypes, propsone, propstwo, zetas


def make_typesplot(types, propsone, propstwo, zetas, numfeatures, cutoff, contrast, typescatterfile):
    print("----make_typesplot")
    plot = pygal.XY(style=zeta_style,
                    show_legend=False,
                    range=(0, 1),
                    show_y_guides=True,
                    show_x_guides=True,
                    title="Verteilung der Type-Anteile",
                    x_title="Anteil der Types in " + str(contrast[1]),
                    y_title="Anteil der Types in " + str(contrast[2]))
    for i in range(0, numfeatures * 2):
        if zetas[i] > cutoff:
            color = "green"
            size = 4
        elif zetas[i] < -cutoff:
            color = "blue"
            size = 4
        else:
            color = "grey"
            size = 3
        plot.add(str(types[i]), [
            {"value": (propsone[i], propstwo[i]), "label": "zeta " + str(zetas[i]), "color": color,
             "node": {"r": size}}])
        plot.add("orientation", [(0, 0.3), (0.7, 1)], stroke=True, show_dots=False,
                 stroke_style={'width': 0.3, 'dasharray': '2, 6'})
        plot.add("orientation", [(0, 0.6), (0.4, 1)], stroke=True, show_dots=False,
                 stroke_style={'width': 0.3, 'dasharray': '2, 6'})
        plot.add("orientation", [(0.3, 0), (1, 0.7)], stroke=True, show_dots=False,
                 stroke_style={'width': 0.3, 'dasharray': '2, 6'})
        plot.add("orientation", [(0.6, 0), (1, 0.4)], stroke=True, show_dots=False,
                 stroke_style={'width': 0.3, 'dasharray': '2, 6'})
        plot.add("orientation", [(0, 0), (1, 1)], stroke=True, show_dots=False,
                 stroke_style={'width': 0.3, 'dasharray': '2, 6'})
    plot.render_to_file(typescatterfile)


def plot_types(numfeatures, cutoff, contrast, contraststring, parameterstring, resultsfolder):
    """
    Function to make a scatterplot with the type proprtion data.
    """
    print("--plot_types")
    zetascorefile = resultsfolder + "zetascores_" + contraststring + "_" + parameterstring + ".csv"
    typescatterfile = (resultsfolder + "typescatter_" + contraststring + "_"
                       + parameterstring + "-" + str(numfeatures) + "-" + str(cutoff) + ".svg")
    scores = get_scores(zetascorefile, numfeatures)
    thetypes, propsone, propstwo, zetas = make_data(scores)
    make_typesplot(thetypes, propsone, propstwo, zetas, numfeatures, cutoff, contrast, typescatterfile)
    print("Done.")


# ==============================================
# Threeway comparison
# ==============================================

threeway_style = pygal.style.Style(
    background = 'white',
    plot_background = 'white',
    font_family = "FreeSans",
    guide_stroke_dasharray = (6,6),
    major_guide_stroke_dasharray = (1,1),
    title_font_size = 16,
    legend_font_size = 14,
    label_font_size = 12,
    major_label_font_size = 12,
    value_font_size = 12,
    major_value_font_size = 12,
    tooltip_font_size = 12,
    opacity_hover = 0.2,
    colors = ("firebrick", "mediumblue", "green"))


def get_distfeatures(zetascorefile, numfeatures):
    print("----get_distfeatures")
    with open(zetascorefile, "r") as infile:
        allzetascores = pd.DataFrame.from_csv(infile, sep="\t")
        allzetascores["type"] = allzetascores.index
        distscoreshead = allzetascores.head(numfeatures)
        distscorestail = allzetascores.tail(numfeatures)
        distscoresall = distscoreshead.append(distscorestail)
        distfeatures = list(distscoresall.loc[:, "type"])
        # print("distfeatures", distfeatures)
        return distfeatures


def select_distrawcounts(featuresfile, distfeatures):
    print("----select_distrawcounts")
    with open(featuresfile, "r") as infile:
        allcounts = pd.DataFrame.from_csv(infile, sep="\t")
        allcounts["type"] = allcounts.index
        # print(allcounts.head())
        distrawcounts = allcounts[allcounts["type"].isin(distfeatures)]
        distrawcounts = distrawcounts.drop("type", axis=1)
        # print(distrawcounts.head())
        return distrawcounts


def calculate_distprops(distrawcounts, group):
    print("----calculate_distprops")
    distprops = np.sum(distrawcounts, axis=1).divide(len(distrawcounts.columns), axis=0)
    distprops = pd.Series(distprops, name=group)
    # print(distprops)
    return distprops


def load_dataframe(distpropsfile):
    with open(distpropsfile, "r") as infile:
        alldistprops = pd.DataFrame.from_csv(infile, sep="\t")
        # print(alldistprops.head())
        return alldistprops


def make_dotplot(alldistprops, sortby, dotplotfile):
    print("----make_dotplot")
    alldistprops = alldistprops.T
    alldistprops = alldistprops.sort_values(sortby, axis=0, ascending="False")
    alldistprops = alldistprops.T
    dotplot = pygal.Dot(style=threeway_style,
                        show_legend=False,
                        legend_at_bottom=True,
                        legend_at_bottom_columns=3,
                        show_y_guides=True,
                        show_x_guides=False,
                        x_label_rotation=60,
                        title="Vergleich dreier Gruppen\n(Anteil der Segmente pro Gruppe)",
                        x_title="Distinktive Types",
                        y_title="Textgruppen")
    distfeatures = alldistprops.columns
    dotplot.x_labels = distfeatures
    for i in range(0,3):
        grouplabel = alldistprops.index[i]
        distprops = list(alldistprops.loc[alldistprops.index[i],:])
        dotplot.add(grouplabel, distprops)
    dotplot.render_to_file(dotplotfile)


def make_lineplot(alldistprops, sortby, lineplotfile):
    print("----make_lineplot")
    if sortby == "zetascores":
        alldistprops = alldistprops.T
        alldistprops[sortby] = alldistprops.loc[:,"comedie"] - alldistprops.loc[:,"tragedie"]
        alldistprops = alldistprops.sort_values(sortby, axis=0, ascending=False)
        print(alldistprops)
        alldistprops = alldistprops.T
    else:
        alldistprops = alldistprops.T
        alldistprops = alldistprops.sort_values(sortby, axis=0, ascending="True")
        alldistprops = alldistprops.T
    lineplot = pygal.Line(style=threeway_style,
                    show_legend=True,
                    legend_at_bottom=True,
                    legend_at_bottom_columns=3,
                    show_y_guides=False,
                    show_x_guides=False,
                    x_label_rotation=60,
                    title="Vergleich dreier Gruppen",
                    x_title="Distinktive Types",
                    y_title="Anteil der Segmente",
                    interpolate='cubic')
    distfeatures = alldistprops.columns
    lineplot.x_labels = distfeatures
    for i in range(0,3):
        grouplabel = alldistprops.index[i]
        distprops = list(alldistprops.loc[alldistprops.index[i],:])
        lineplot.add(grouplabel, distprops)
        lineplot.render_to_file(lineplotfile)


def test_correlations(alldistprops):
    print("----test_correlations")
    columnlabels = ["groupone", "grouptwo", "correlation", "p-value"]
    allcorrinfos = []
    for i,j in [(0,1), (0,2), (1,2)]:
        comparison = [alldistprops.index[i], alldistprops.index[j]]
        correlation = stats.pearsonr(list(alldistprops.loc[alldistprops.index[i],:]),
                                     list(alldistprops.loc[alldistprops.index[j],:]))
        corrinfo = [comparison[0], comparison[1], correlation[0], correlation[1]]
        allcorrinfos.append(corrinfo)
    allcorrinfosdf = pd.DataFrame(allcorrinfos, columns=columnlabels)
    allcorrinfosdf.sort_values(by="p-value", ascending=True, inplace=True)
    # print(allcorrinfosdf)
    return allcorrinfosdf


# Coordinating function
def threeway(datafolder, resultsfolder, contrast, contraststring, parameterstring,
             thirdgroup, numfeatures, sortby, mode):
    print("--threeway")
    # Create necessary filenames
    zetascorefile = resultsfolder + "zetascores_" + contraststring + "_" + parameterstring + ".csv"
    dotplotfile = resultsfolder + "dotplot_" + contraststring + "-" + thirdgroup[1] + "_" + parameterstring + "-" + str(numfeatures) + ".svg"
    lineplotfile = resultsfolder + "lineplot_" + contraststring + "-" + thirdgroup[1] + "_" + parameterstring + "-" + str(numfeatures) + ".svg"
    distpropsfile = datafolder + "distprops_" + contraststring + "_" + parameterstring + "-" + str(numfeatures) + ".csv"
    correlationsfile = resultsfolder + "correlations_" + contraststring + "-" + thirdgroup[1] + "_" + parameterstring + "-" + str(numfeatures) + ".csv"
    # Do the actual work
    if mode == "generate":
        # Calculate the proportions for each feature for the three groups
        distfeatures = get_distfeatures(zetascorefile, numfeatures)
        alldistprops = pd.DataFrame()
        for group in (contrast[1], contrast[2], thirdgroup[1]):
            featuresfile = datafolder + "features_" + group + "_" + parameterstring + ".csv"
            distrawcounts = select_distrawcounts(featuresfile, distfeatures)
            distprops = calculate_distprops(distrawcounts, group)
            alldistprops = alldistprops.append(distprops)
        save_dataframe(alldistprops, distpropsfile)
        # Visualize the data and make a correlation test
        # make_dotplot(alldistprops, sortby, dotplotfile)
        make_lineplot(alldistprops, sortby, lineplotfile)
        correlationscoresdf = test_correlations(alldistprops)
        save_dataframe(correlationscoresdf, correlationsfile)
    if mode == "analyze":
        # Load data from a previous "generate" step
        alldistprops = load_dataframe(distpropsfile)
        # print(alldistprops)
        # Visualize the data and make a correlation test
        # make_dotplot(alldistprops, sortby, dotplotfile)
        make_lineplot(alldistprops, sortby, lineplotfile)
        correlationscoresdf = test_correlations(alldistprops)
        save_dataframe(correlationscoresdf, correlationsfile)
