"""The "default font name" of a FACE_NAME record (attribute bit 5, rule HW80).

Hangul 2024 writes it when it saves a HWPX as .hwp: for a font without a substitute font (`hh:substFont`) the English name of the
font, which the HWPX does not carry. The table is read from the 64 font names (+ 38 measured in Hangul, rule HW95) of 153 government forms (Hangul's own .hwp of the
same HWPX, one name each, no conflict, no font without a substitute font lacks it). A name outside the table: the record is
written without a default name.
"""

DEFAULT_FONT_NAME = {
    '#그래픽': '#Graphic', '#디나루': '#Dinaru', '#세고딕': '#Segothic', '#세명조': '#Semyeongjo', '#신디나루': '#Sindinaru',
    '#신명조': '#Sinmyeongjo', '#신세고딕': '#Sinsegothic', '#신태명조': '#Sintaemyeongjo', '#중고딕': '#Junggothic',
    '#중명조': '#Jungmyeongjo', '#태고딕': '#Taegothic', '#태명조': '#Taemyeongjo', 'Arial': 'Arial', 'Calibri': 'Calibri',
    'HCI Hollyhock': 'HCI Hollyhock', 'HCI Poppy': 'HCI Poppy', 'HCI Tulip': 'HCI Tulip', 'HY견고딕': 'HYGothic-Extra',
    'HY견명조': 'HYMyeongJo-Extra', 'HY바다L': 'HYbdaL', 'HY신명조': 'HYSinMyeongJo-Medium', 'HY울릉도B': 'HYwulB',
    'HY헤드라인M': 'HYHeadLine-Medium', 'Times New Roman': 'Times New Roman', '가는안상수체': '가는안상수체', '고딕': 'Gothic',
    '굴림': 'Gulim', '굴림체': 'GulimChe', '궁서': 'Gungsuh', '궁서체': 'GungsuhChe', '돋움': 'Dotum', '돋움체': 'DotumChe',
    '맑은 고딕': 'Malgun Gothic', '명조': 'Myeongjo', '바탕': 'Batang', '바탕체': 'BatangChe', '산세리프': 'Sans Serif',
    '새굴림': 'New Gulim', '신명 견명조': 'Sinmyeong Gyeonmyeongjo', '신명 디나루': 'Sinmyeong Dinaru',
    '신명 세명조': 'Sinmyeong Semyeongjo', '신명 신명조': 'Sinmyeong Sinmyeongjo', '신명 신신명조': 'Sinmyeong Sinsinmyeongjo',
    '신명 중고딕': 'Sinmyeong Junggothic', '신명 중명조': 'Sinmyeong Jungmyeongjo', '신명 태고딕': 'Sinmyeong Taegothic',
    '신명 태그래픽': 'Sinmyeong Taegraphic', '신명 태명조': 'Sinmyeong Taemyeongjo', '신명조 약자': 'Sinmyeongjo Jananese',
    '펜흘림': '펜흘림', '필기': 'Pilgi', '한양견고딕': 'HY Gyeongothic', '한양견명조': 'HY Gyeonmyeongjo', '한양궁서': 'HY Gungseo',
    '한양신명조': 'HY Sinmyeongjo', '한양신명조V': 'HY Sinmyeongjo V', '한양중고딕': 'HY Junggothic', '한컴바탕': 'Haansoft Batang',
    '함초롬돋움': 'HCR Dotum', '함초롬돋움 확장': 'HCR Dotum Ext', '함초롬바탕': 'HCR Batang', '휴먼고딕': '휴먼고딕',
    '휴먼명조': '휴먼명조', '휴먼옛체': 'Yet R',
    # 38 more, measured in Hangul 2024 itself (HW95): the font as an extra HANGUL font of a Hangul-made HWPX, used by a paragraph, saved as .hwp
    'HY궁서B': 'HYGungSo-Bold', 'HY그래픽': 'HYgprM', 'HY그래픽M': 'HYGraphic-Medium', 'HY동녘M': 'HYdnkM', 'HY수평선B': 'HYsupB',
    'HY수평선M': 'HYsupM', 'HY엽서M': 'HYPost-Medium', 'HY울릉도M': 'HYwulM', 'HY중고딕': 'HYGothic-Medium', 'HY크리스탈M': 'HYcysM',
    'HY태백B': 'HYtbrB', 'MD솔체': 'MDSol', 'MD이솝체': 'MDEasop', 'Noto Sans KR': 'Noto Sans KR', '안상수2006굵은': 'ahn2006-B',
    '양재난초체M': 'Yj NANCHO Medium', '양재백두체B': 'Yj BACDOO Bold', '양재튼튼체B': 'Yj TEUNTEUN Bold', '태 나무': '태 나무',
    '한양해서': 'HYhaeseo', '한컴 고딕': 'Hancom Gothic Regular', '한컴 말랑말랑 Bold': 'Hancom MalangMalang Bold',
    '한컴 소망 B': 'Haan Somang B', '한컴 소망 M': 'Haan Somang M', '한컴 윤고딕 230': 'Haan YGodic 230',
    '한컴 윤고딕 240': 'Haan YGodic 240', '한컴 윤고딕 250': 'Haan YGodic 250', '한컴 윤고딕 760': 'Haan YoonGothic760',
    '한컴 윤체 B': 'Haan YHead B', '한컴 쿨재즈 B': 'Haan Cooljazz B', '한컴돋움': 'Haansoft Dotum',
    '한컴산뜻돋움': 'Han Santteut Dotum Regular', '함초롬바탕 확장B': 'HCR Batang ExtB', '휴먼굵은팸체': '휴먼굵은팸체',
    '휴먼둥근헤드라인': 'Headline R', '휴먼매직체': 'Magic R', '휴먼모음T': 'MoeumT R', '휴먼엑스포': 'Expo M',
}


# The serif style byte of the PANOSE type info of a FACE_NAME record. The HWPX has no such attribute (familyType is FCAT_GOTHIC for
# every font in the HWPX of Hangul and of hwp2hwpx); Hangul 2024 writes it by font name, and 11 for the slot whose type info has
# proportion 4 and letterform 2 (the OTHER language slot). Read from 80 (font, type info) pairs of 153 forms: the 63 names below
# and that rule give all 80 (no mismatch). A font with a substitute font gets bytes that change from file to file: not compared.
SERIF_STYLE = {
    '#그래픽': 0, '#디나루': 0, '#세고딕': 0, '#세명조': 0, '#신디나루': 0, '#신명조': 0, '#신세고딕': 0, '#신태명조': 0, '#중고딕': 0, '#중명조': 0, '#태고딕': 0,
    '#태명조': 0, 'Calibri': 15, 'HCI Hollyhock': 0, 'HCI Poppy': 0, 'HCI Tulip': 0, 'HY견고딕': 3, 'HY견명조': 3, 'HY바다L': 3,
    'HY신명조': 3, 'HY울릉도B': 3, 'HY헤드라인M': 3, 'Times New Roman': 2, '가는안상수체': 1, '고딕': 0, '굴림': 11, '굴림체': 11, '궁서': 3, '궁서체': 3,
    '돋움': 11, '돋움체': 11, '맑은 고딕': 11, '명조': 0, '바탕': 3, '바탕체': 3, '산세리프': 0, '새굴림': 3, '신명 견명조': 0, '신명 디나루': 0, '신명 세명조': 0,
    '신명 신명조': 0, '신명 신신명조': 0, '신명 중고딕': 0, '신명 중명조': 0, '신명 태고딕': 0, '신명 태그래픽': 0, '신명 태명조': 0, '신명조 약자': 0, '펜흘림': 3,
    '필기': 0, '한양견고딕': 0, '한양견명조': 0, '한양궁서': 0, '한양신명조': 0, '한양신명조V': 0, '한양중고딕': 0, '한컴바탕': 3, '함초롬돋움': 11, '함초롬돋움 확장': 3,
    '함초롬바탕': 3, '휴먼고딕': 1, '휴먼명조': 1, '휴먼옛체': 3,
}
