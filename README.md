# Canvas To Coursera

Script to convert from a Canvas course shell into Coursera import documents(s) containing
quiz and question banks in a text format exoected by the
[Coursera Quiz Questions Import Template](https://www.coursera.org/template-documents/coursera-quiz-questions-import-template)

## Example Usage

1. Export your canvas course (exporting quizzes is not enough, you need the full course).
2. Rename the resulting `.imscc` file `.zip` and extract to a directory.
3. Install Python 3.7 or later on your host.
4. Run the command below, substituting the export_path argument with the location of your extracted
.imscc file: 
```
python3 canvas_to_coursera --export_path="C:\path\to\export\directory"
```

Text files in the format expected by [Coursera Quiz Questions Import Template](https://www.coursera.support/s/article/360026695752-Use-Shareable-Templates-to-Create-Course-Content?)
will be found in the `export_path` directory after the script completes.

## Not Yet Implemented/Future Work

* Support for exporting feedback from Canvas is not implemented, however a Feedback item
is placed in text output for incorrect question types.
* See the CourseraQuestion class for list of supported question types.  Note that the support
for `matching_question` is rudimentary, you'll need to review and edit these before you can import.  Search
the output file for `converted_matcihng_question` to find questions which likely need review.
* Complicated grading scenarios like different weighting for answers are not fully supported.
* Embedded images are not supported, you'll need to migrate these by hand.
* I Suggest spot checking/double checking reading through all content and corrected answers.  I wrote this
as a way to save myself a bunch of work copy and pasting rather than a production ready tool!  
