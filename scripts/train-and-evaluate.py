#!/usr/bin/env python
"""
TODO: Add different example weighting.
"""

import sys, string
from common.stats import stats
from common.file import myopen

from os.path import join
import os.path, os
from os.path import join
BASEDIR = os.path.split(os.path.abspath(os.path.dirname(__file__)))[0]

CATEGORIES_FILENAME = join(BASEDIR, "data/train/Categories.txt")
DEV_TRAIN_FILENAME = join(BASEDIR, "data/train/CategorizedQuerySample.txt")

from optparse import OptionParser
parser = OptionParser()
parser.add_option("-n", "--name", dest="name", help="Name of this run")
parser.add_option("--dev", dest="dev", action="store_true", help="Train on train-partition and evaluate on dev-partiton", default=True)
parser.add_option("--test", dest="dev", action="store_false", help="Train on train and evaluate on dev")
parser.add_option("--l2", dest="l2", help="l2 sigma", type="string")
parser.add_option("-b", "--brown", dest="brown", action="append", help="brown clusters to use")
parser.add_option("-e", "--embedding", dest="embedding", action="append", help="embedding to use")
parser.add_option("--brown-prefixes", dest="prefixes", default="4,6,10,20", help="brown prefixes")
parser.add_option("--dont-balance-examples", dest="balanceexamples", action="store_false", help="Don't balance weight of positive examples against negative examples", default=False)
parser.add_option("--balance-examples", dest="balanceexamples", action="store_true", help="Balance weight of positive examples against negative examples")
(options, args) = parser.parse_args()
assert len(args) == 0
assert options.name is not None
assert options.l2 is not None

if options.dev:
    TRAIN_FILENAME = join(BASEDIR, "data/train/CategorizedQuerySample.train-partition.txt")
    EVAL_FILENAMES = [join(BASEDIR, "data/train/CategorizedQuerySample.dev-partition.txt")]
else:
    TRAIN_FILENAME = join(BASEDIR, "data/train/CategorizedQuerySample.txt")
    EVAL_FILENAMES = [join(BASEDIR, "data/test/labeler1.txt"),join(BASEDIR, "data/test/labeler2.txt"),join(BASEDIR, "data/test/labeler3.txt")]

all_labels, origlabel_to_newlabel = None, None
def read_labels():
    global all_labels, origlabel_to_newlabel

    # Read labels
    all_labels = []
    origlabel_to_newlabel = {}
    for l in open(CATEGORIES_FILENAME):
        l = string.strip(l)
        origl = l
#        l = string.replace(l, "\\", ":")
        l = string.replace(l, "\\", "_")
        l = string.replace(l, "=", "_")
        l = string.replace(l, " ", "_")
        l = string.replace(l, "&", "AND")
        all_labels.append(l)
        origlabel_to_newlabel[origl] = l

def read_labeled_queries(filename):
    """
    Read a labeled queries file.
    Return a list of (query, list of labels)
    """
    examples = []
    for e in open(filename):
        v = string.split(string.strip(e), "\t")
        query = v[0]
#        print >> sys.stderr, query
        labels = [origlabel_to_newlabel[string.strip(l)] for l in v[1:]]
#        print >> sys.stderr, query, labels
        morefeatures = ""
        for w in string.split(query):
            for bi in range(len(word_to_cluster)):
                if w not in word_to_cluster[bi]:
                    print >> sys.stderr, "Word not in Brown:", w
                else:
                    for p in prefixes:
                        morefeatures += " BROWN.%d.p%d.%s" % (bi, p, word_to_cluster[bi][w][:p])
#        print >> sys.stderr, query
#        print >> sys.stderr, morefeatures
        examples.append((query + " " + morefeatures, labels))
    return examples

def run(cmd):
    print >> sys.stderr, cmd
    print >> sys.stderr, stats()
    os.system(cmd)
    print >> sys.stderr, stats()



prefixes = [int(s) for s in string.split(options.prefixes, sep=",")]

if options.brown is None: options.brown = []
word_to_cluster = []
for i, brownfile in enumerate(options.brown):
    print >> sys.stderr, "Reading Brown file: %s" % brownfile
    word_to_cluster.append({})
    assert len(word_to_cluster) == i+1
    for l in myopen(brownfile):
        cluster, word, cnt = string.split(l)
        word_to_cluster[i][word] = cluster

if options.embedding is None: options.embedding = []
word_to_embedding = []
for i, embeddingfile in enumerate(options.embedding):
    print >> sys.stderr, "Reading Embedding file: %s" % embeddingfile
    word_to_embedding.append({})
    assert len(word_to_embedding) == i+1
    for l in myopen(embeddingfile):
        sp = string.split(l)
        word_to_embedding[i][sp[0]] = [float(v)*options.embeddingscale for v in sp[1:]]

assert len(word_to_embedding) == 0


if options.dev: workdir = join(BASEDIR, "work/%s/dev/" % options.name)
else: workdir = join(BASEDIR, "work/%s/test/" % options.name)
print >> sys.stderr, "Working in directory: %s" % workdir
if not os.path.exists(workdir): os.makedirs(workdir)
assert os.path.isdir(workdir)

read_labels()

target_is_prediction = [0] * len(EVAL_FILENAMES)
target_is_true = [0] * len(EVAL_FILENAMES)
prediction_is_true = [0] * len(EVAL_FILENAMES)

scorefile = join(workdir, "evaluation.l2-%s.txt" % (options.l2))
if os.path.exists(scorefile):
    print >> sys.stderr, "%s exists. STOPPING" % scorefile
    sys.exit(1)

# Generate features
for l in all_labels:
    featurestrainfile = join(workdir, "features.train.l2-%s.%s.txt" % (options.l2, l))
    f = open(featurestrainfile, "wt")

    valcnt = [0, 0]
    if options.balanceexamples:
        for query, labels in read_labeled_queries(TRAIN_FILENAME):
            y = int(l in labels)
            valcnt[y] += 1
    else:
        valcnt = [1, 1]
    weight = [0,0]
    weight[0] = 1. * valcnt[1] / (valcnt[0] + valcnt[1])
    weight[1] = 1. * valcnt[0] / (valcnt[0] + valcnt[1])
    if weight[0] == 0 or weight[1] == 0: weight = [1,1]
    for query, labels in read_labeled_queries(TRAIN_FILENAME):
        y = int(l in labels)
        f.write("%d $$$WEIGHT %f %s\n" % (y, weight[y], query))
    f.close()

    modelfile = join(workdir, "model.l2-%s.%s.txt" % (options.l2, l))
    modelerrfile = join(workdir, "model.l2-%s.%s.err" % (options.l2, l))

    cmd = "megam -lambda %s binary %s > %s 2> %s" % (options.l2, featurestrainfile, modelfile, modelerrfile)
    run(cmd)

    for i in range(len(EVAL_FILENAMES)):
        featuresevalfile = join(workdir, "features.eval%d.l2-%s.%s.txt" % (i, options.l2, l))
        f = open(featuresevalfile, "wt")
        target = []
        for query, labels in read_labeled_queries(EVAL_FILENAMES[i]):
            target.append(int(l in labels))
            f.write("%d %s\n" % (target[-1], query))
        f.close()

        predictedevalfile = join(workdir, "predicted.eval%d.l2-%s.%s.txt" % (i, options.l2, l))
        cmd = "megam -predict %s binary %s > %s 2> /dev/null" % (modelfile, featuresevalfile, predictedevalfile)
        run(cmd)

        predicted = []
        for p in open(predictedevalfile):
#            print >> sys.stderr, string.split(p)[0]
            predicted.append(int(string.split(p)[0]))

        for (t, p) in zip(target, predicted):
#            print >> sys.stderr, t, p
            if t == 1 and p == 1: target_is_prediction[i] += 1
            if t == 1: target_is_true[i] += 1
            if p == 1: prediction_is_true[i] += 1
#            print >> sys.stderr, target_is_prediction[i], target_is_true[i], prediction_is_true[i]

totprc = 0.
totrcl = 0.
totfms = 0.
for i in range(len(EVAL_FILENAMES)):
    if prediction_is_true[i] == 0: prc = 0.
    else: prc = (100. * target_is_prediction[i]/prediction_is_true[i])
    if target_is_true[i] == 0: rcl = 0.
    else: rcl = (100. * target_is_prediction[i]/target_is_true[i])
    if prc + rcl == 0: fms = 0
    else: fms = 2 * prc * rcl / (prc + rcl)

    print "Precision %d: %.2f" % (i, prc)
    print "Recall %d: %.2f" % (i, rcl)
    print "F-measure %d: %.2f" % (i, fms)

    totprc += prc
    totrcl += rcl
    totfms += fms

totprc /= len(EVAL_FILENAMES)
totrcl /= len(EVAL_FILENAMES)
totfms /= len(EVAL_FILENAMES)

if len(EVAL_FILENAMES) > 1:
    print "Mean Precision: %.2f" % (totprc)
    print "Mean Recall: %.2f" % (totrcl)
    print "Mean F-measure: %.2f" % (totfms)

f = open(scorefile, "wt")
f.write("Precision: %.2f\n" % (totprc))
f.write("Recall: %.2f\n" % (totrcl))
f.write("F-measure: %.2f\n" % (totfms))
f.close()
