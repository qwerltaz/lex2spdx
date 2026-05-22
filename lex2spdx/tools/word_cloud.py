"""Make a word cloud from a csv file."""

import matplotlib.pyplot as plt
from wordcloud import WordCloud

from .. import cvar


def main():
    input_file = cvar.data_dir / "top_17689_popular_licenses_text_only.csv"

    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    wordcloud = WordCloud(width=1000, height=2000, max_words=1000, background_color="white",
                          collocations=False, prefer_horizontal=1.0)

    wordcloud.generate(text)

    wordcloud.to_file("word_cloud.png")

    plt.imshow(wordcloud, interpolation="bicubic")
    plt.axis("off")
    plt.show()


if __name__ == '__main__':
    main()
