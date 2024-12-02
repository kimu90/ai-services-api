--
-- PostgreSQL database dump
--

-- Dumped from database version 15.10
-- Dumped by pg_dump version 15.10

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: author_publication; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.author_publication (
    author_id integer NOT NULL,
    doi character varying(255) NOT NULL
);


ALTER TABLE public.author_publication OWNER TO postgres;

--
-- Name: authors; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.authors (
    author_id integer NOT NULL,
    name text NOT NULL,
    orcid character varying(255),
    author_identifier character varying(255)
);


ALTER TABLE public.authors OWNER TO postgres;

--
-- Name: authors_author_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.authors_author_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.authors_author_id_seq OWNER TO postgres;

--
-- Name: authors_author_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.authors_author_id_seq OWNED BY public.authors.author_id;


--
-- Name: experts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.experts (
    orcid character varying(255) NOT NULL,
    firstname character varying(255) NOT NULL,
    lastname character varying(255) NOT NULL,
    domains text[],
    fields text[],
    subfields text[]
);


ALTER TABLE public.experts OWNER TO postgres;

--
-- Name: publication_tag; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.publication_tag (
    publication_doi character varying(255) NOT NULL,
    tag_id integer NOT NULL
);


ALTER TABLE public.publication_tag OWNER TO postgres;

--
-- Name: publications; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.publications (
    doi character varying(255) NOT NULL,
    title text NOT NULL,
    abstract text,
    summary text
);


ALTER TABLE public.publications OWNER TO postgres;

--
-- Name: query_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.query_history (
    query_id integer NOT NULL,
    query text NOT NULL,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    result_count integer,
    search_type character varying(50)
);


ALTER TABLE public.query_history OWNER TO postgres;

--
-- Name: query_history_query_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.query_history_query_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.query_history_query_id_seq OWNER TO postgres;

--
-- Name: query_history_query_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.query_history_query_id_seq OWNED BY public.query_history.query_id;


--
-- Name: tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tags (
    tag_id integer NOT NULL,
    tag_name character varying(255) NOT NULL
);


ALTER TABLE public.tags OWNER TO postgres;

--
-- Name: tags_tag_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tags_tag_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.tags_tag_id_seq OWNER TO postgres;

--
-- Name: tags_tag_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tags_tag_id_seq OWNED BY public.tags.tag_id;


--
-- Name: term_frequencies; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.term_frequencies (
    term_id integer NOT NULL,
    term text NOT NULL,
    frequency integer DEFAULT 1,
    last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.term_frequencies OWNER TO postgres;

--
-- Name: term_frequencies_term_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.term_frequencies_term_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.term_frequencies_term_id_seq OWNER TO postgres;

--
-- Name: term_frequencies_term_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.term_frequencies_term_id_seq OWNED BY public.term_frequencies.term_id;


--
-- Name: authors author_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.authors ALTER COLUMN author_id SET DEFAULT nextval('public.authors_author_id_seq'::regclass);


--
-- Name: query_history query_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.query_history ALTER COLUMN query_id SET DEFAULT nextval('public.query_history_query_id_seq'::regclass);


--
-- Name: tags tag_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags ALTER COLUMN tag_id SET DEFAULT nextval('public.tags_tag_id_seq'::regclass);


--
-- Name: term_frequencies term_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.term_frequencies ALTER COLUMN term_id SET DEFAULT nextval('public.term_frequencies_term_id_seq'::regclass);


--
-- Data for Name: author_publication; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.author_publication (author_id, doi) FROM stdin;
1	https://doi.org/10.1016/s0140-6736(14)60460-8
2	https://doi.org/10.1016/s0140-6736(14)60460-8
3	https://doi.org/10.1016/s0140-6736(14)60460-8
4	https://doi.org/10.1016/s0140-6736(14)60460-8
5	https://doi.org/10.1016/s0140-6736(14)60460-8
6	https://doi.org/10.1016/s0140-6736(14)60460-8
7	https://doi.org/10.1016/s0140-6736(14)60460-8
8	https://doi.org/10.1016/s0140-6736(14)60460-8
9	https://doi.org/10.1016/s0140-6736(14)60460-8
10	https://doi.org/10.1016/s0140-6736(14)60460-8
11	https://doi.org/10.1016/s0140-6736(14)60460-8
12	https://doi.org/10.1016/s0140-6736(14)60460-8
13	https://doi.org/10.1016/s0140-6736(14)60460-8
14	https://doi.org/10.1016/s0140-6736(14)60460-8
15	https://doi.org/10.1016/s0140-6736(14)60460-8
16	https://doi.org/10.1016/s0140-6736(14)60460-8
17	https://doi.org/10.1016/s0140-6736(14)60460-8
18	https://doi.org/10.1016/s0140-6736(14)60460-8
19	https://doi.org/10.1016/s0140-6736(14)60460-8
20	https://doi.org/10.1016/s0140-6736(14)60460-8
21	https://doi.org/10.1016/s0140-6736(14)60460-8
22	https://doi.org/10.1016/s0140-6736(14)60460-8
23	https://doi.org/10.1016/s0140-6736(14)60460-8
24	https://doi.org/10.1016/s0140-6736(14)60460-8
25	https://doi.org/10.1016/s0140-6736(14)60460-8
26	https://doi.org/10.1016/s0140-6736(14)60460-8
27	https://doi.org/10.1016/s0140-6736(14)60460-8
28	https://doi.org/10.1016/s0140-6736(14)60460-8
29	https://doi.org/10.1016/s0140-6736(14)60460-8
30	https://doi.org/10.1016/s0140-6736(14)60460-8
31	https://doi.org/10.1016/s0140-6736(14)60460-8
32	https://doi.org/10.1016/s0140-6736(14)60460-8
33	https://doi.org/10.1016/s0140-6736(14)60460-8
34	https://doi.org/10.1016/s0140-6736(14)60460-8
35	https://doi.org/10.1016/s0140-6736(14)60460-8
36	https://doi.org/10.1016/s0140-6736(14)60460-8
37	https://doi.org/10.1016/s0140-6736(14)60460-8
38	https://doi.org/10.1016/s0140-6736(14)60460-8
39	https://doi.org/10.1016/s0140-6736(14)60460-8
40	https://doi.org/10.1016/s0140-6736(14)60460-8
41	https://doi.org/10.1016/s0140-6736(14)60460-8
42	https://doi.org/10.1016/s0140-6736(14)60460-8
43	https://doi.org/10.1016/s0140-6736(14)60460-8
44	https://doi.org/10.1016/s0140-6736(14)60460-8
45	https://doi.org/10.1016/s0140-6736(14)60460-8
46	https://doi.org/10.1016/s0140-6736(14)60460-8
47	https://doi.org/10.1016/s0140-6736(14)60460-8
48	https://doi.org/10.1016/s0140-6736(14)60460-8
49	https://doi.org/10.1016/s0140-6736(14)60460-8
50	https://doi.org/10.1016/s0140-6736(14)60460-8
51	https://doi.org/10.1016/s0140-6736(14)60460-8
52	https://doi.org/10.1016/s0140-6736(14)60460-8
53	https://doi.org/10.1016/s0140-6736(14)60460-8
54	https://doi.org/10.1016/s0140-6736(14)60460-8
55	https://doi.org/10.1016/s0140-6736(14)60460-8
56	https://doi.org/10.1016/s0140-6736(14)60460-8
57	https://doi.org/10.1016/s0140-6736(14)60460-8
58	https://doi.org/10.1016/s0140-6736(14)60460-8
59	https://doi.org/10.1016/s0140-6736(14)60460-8
60	https://doi.org/10.1016/s0140-6736(14)60460-8
61	https://doi.org/10.1016/s0140-6736(14)60460-8
62	https://doi.org/10.1016/s0140-6736(14)60460-8
63	https://doi.org/10.1016/s0140-6736(14)60460-8
64	https://doi.org/10.1016/s0140-6736(14)60460-8
65	https://doi.org/10.1016/s0140-6736(14)60460-8
66	https://doi.org/10.1016/s0140-6736(14)60460-8
67	https://doi.org/10.1016/s0140-6736(14)60460-8
68	https://doi.org/10.1016/s0140-6736(14)60460-8
69	https://doi.org/10.1016/s0140-6736(14)60460-8
70	https://doi.org/10.1016/s0140-6736(14)60460-8
71	https://doi.org/10.1016/s0140-6736(14)60460-8
72	https://doi.org/10.1016/s0140-6736(14)60460-8
73	https://doi.org/10.1016/s0140-6736(14)60460-8
74	https://doi.org/10.1016/s0140-6736(14)60460-8
75	https://doi.org/10.1016/s0140-6736(14)60460-8
76	https://doi.org/10.1016/s0140-6736(14)60460-8
77	https://doi.org/10.1016/s0140-6736(14)60460-8
78	https://doi.org/10.1016/s0140-6736(14)60460-8
79	https://doi.org/10.1016/s0140-6736(14)60460-8
80	https://doi.org/10.1016/s0140-6736(14)60460-8
81	https://doi.org/10.1016/s0140-6736(14)60460-8
82	https://doi.org/10.1016/s0140-6736(14)60460-8
83	https://doi.org/10.1016/s0140-6736(14)60460-8
84	https://doi.org/10.1016/s0140-6736(14)60460-8
85	https://doi.org/10.1016/s0140-6736(14)60460-8
86	https://doi.org/10.1016/s0140-6736(14)60460-8
87	https://doi.org/10.1016/s0140-6736(14)60460-8
88	https://doi.org/10.1016/s0140-6736(14)60460-8
89	https://doi.org/10.1016/s0140-6736(14)60460-8
90	https://doi.org/10.1016/s0140-6736(14)60460-8
91	https://doi.org/10.1016/s0140-6736(14)60460-8
92	https://doi.org/10.1016/s0140-6736(14)60460-8
93	https://doi.org/10.1016/s0140-6736(14)60460-8
94	https://doi.org/10.1016/s0140-6736(14)60460-8
95	https://doi.org/10.1016/s0140-6736(14)60460-8
96	https://doi.org/10.1016/s0140-6736(14)60460-8
97	https://doi.org/10.1016/s0140-6736(14)60460-8
98	https://doi.org/10.1016/s0140-6736(14)60460-8
99	https://doi.org/10.1016/s0140-6736(14)60460-8
100	https://doi.org/10.1016/s0140-6736(14)60460-8
101	https://doi.org/10.1016/s0140-6736(15)60901-1
102	https://doi.org/10.1016/s0140-6736(15)60901-1
103	https://doi.org/10.1016/s0140-6736(15)60901-1
104	https://doi.org/10.1016/s0140-6736(15)60901-1
105	https://doi.org/10.1016/s0140-6736(15)60901-1
106	https://doi.org/10.1016/s0140-6736(15)60901-1
107	https://doi.org/10.1016/s0140-6736(15)60901-1
108	https://doi.org/10.1016/s0140-6736(15)60901-1
109	https://doi.org/10.1016/s0140-6736(15)60901-1
110	https://doi.org/10.1016/s0140-6736(15)60901-1
111	https://doi.org/10.1016/s0140-6736(15)60901-1
112	https://doi.org/10.1016/s0140-6736(15)60901-1
113	https://doi.org/10.1016/s0140-6736(15)60901-1
114	https://doi.org/10.1016/s0140-6736(15)60901-1
115	https://doi.org/10.1016/s0140-6736(15)60901-1
116	https://doi.org/10.1016/s0140-6736(15)60901-1
117	https://doi.org/10.1016/s0140-6736(15)60901-1
118	https://doi.org/10.1016/s0140-6736(15)60901-1
119	https://doi.org/10.1016/s0140-6736(15)60901-1
120	https://doi.org/10.1016/s0140-6736(15)60901-1
121	https://doi.org/10.1016/s0140-6736(15)60901-1
122	https://doi.org/10.1016/s0140-6736(15)60901-1
123	https://doi.org/10.1016/s0140-6736(12)60072-5
124	https://doi.org/10.1016/s0140-6736(12)60072-5
125	https://doi.org/10.1016/s0140-6736(12)60072-5
126	https://doi.org/10.1016/s0140-6736(12)60072-5
127	https://doi.org/10.1016/s0140-6736(12)60072-5
107	https://doi.org/10.1016/s0140-6736(12)60072-5
128	https://doi.org/10.1016/s0140-6736(12)60072-5
129	https://doi.org/10.1016/s0140-6736(06)69480-4
130	https://doi.org/10.1016/s0140-6736(06)69480-4
107	https://doi.org/10.1016/s0140-6736(06)69480-4
131	https://doi.org/10.1016/s0140-6736(06)69480-4
132	https://doi.org/10.1016/s0140-6736(06)69480-4
133	https://doi.org/10.1016/s0140-6736(06)69480-4
\.


--
-- Data for Name: authors; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.authors (author_id, name, orcid, author_identifier) FROM stdin;
1	Marie Ng	\N	https://openalex.org/A5107896689
2	Tom Fleming	\N	https://openalex.org/A5105974687
3	Margaret S. Robinson	https://orcid.org/0000-0003-0631-0053	https://openalex.org/A5013650036
4	Blake Thomson	https://orcid.org/0000-0002-6433-0338	https://openalex.org/A5020811309
5	Nicholas Graetz	https://orcid.org/0000-0002-4362-2059	https://openalex.org/A5067637394
6	Christopher Margono	\N	https://openalex.org/A5039140290
7	Erin C Mullany	\N	https://openalex.org/A5009638750
8	Stan Biryukov	\N	https://openalex.org/A5023585266
9	Cristiana Abbafati	https://orcid.org/0000-0003-2811-6251	https://openalex.org/A5022331752
10	Semaw Ferede Abera	https://orcid.org/0000-0002-9284-1231	https://openalex.org/A5012390350
11	Jerry Abraham	\N	https://openalex.org/A5044888998
12	Niveen M E Abu-Rmeileh	\N	https://openalex.org/A5112068167
13	Tom Achoki	https://orcid.org/0000-0001-6309-8904	https://openalex.org/A5022723375
14	Fadia AlBuhairan	https://orcid.org/0000-0002-7377-503X	https://openalex.org/A5067357766
15	Zewdie Aderaw Alemu	\N	https://openalex.org/A5033246400
16	Rafael Alfonso	\N	https://openalex.org/A5079694821
17	Mohammed K. Ali	https://orcid.org/0000-0001-7266-2503	https://openalex.org/A5100680450
18	Raghib Ali	https://orcid.org/0000-0002-8225-4674	https://openalex.org/A5017879318
19	Nelson Alvis‐Guzmán	https://orcid.org/0000-0001-9458-864X	https://openalex.org/A5078832673
20	Walid Ammar	\N	https://openalex.org/A5110888093
21	Palwasha Anwari	https://orcid.org/0000-0001-6989-0791	https://openalex.org/A5000535250
22	Amitava Banerjee	https://orcid.org/0000-0001-8741-3411	https://openalex.org/A5072175850
23	Sı́món Barquera	https://orcid.org/0000-0003-1854-4615	https://openalex.org/A5033911261
24	Sanjay Basu	https://orcid.org/0000-0002-0599-6332	https://openalex.org/A5088459011
25	Derrick Bennett	https://orcid.org/0000-0002-9170-8447	https://openalex.org/A5063906396
26	Zulfiqar A Bhutta	https://orcid.org/0000-0003-0637-599X	https://openalex.org/A5031009188
27	Jed D Blore	https://orcid.org/0000-0002-3649-8686	https://openalex.org/A5038109773
28	Norberto Luiz Cabral	https://orcid.org/0000-0001-5829-9699	https://openalex.org/A5085837588
29	Ismael Campos‐Nonato	https://orcid.org/0000-0001-5939-3396	https://openalex.org/A5080693617
30	Jung‐Chen Chang	https://orcid.org/0000-0001-8651-2602	https://openalex.org/A5081221311
31	Rajiv Chowdhury	https://orcid.org/0000-0003-4881-5690	https://openalex.org/A5023059768
32	Karen Courville	https://orcid.org/0000-0002-4182-6736	https://openalex.org/A5005843863
33	Michael H Criqui	\N	https://openalex.org/A5108806687
34	David K Cundiff	https://orcid.org/0000-0002-3206-9665	https://openalex.org/A5082383024
35	Kaustubh Dabhadkar	\N	https://openalex.org/A5019689738
36	Lalit Dandona	https://orcid.org/0000-0002-3114-8628	https://openalex.org/A5103040831
37	Adrian Davis	https://orcid.org/0000-0001-7134-7528	https://openalex.org/A5046431320
38	Anand Dayama	\N	https://openalex.org/A5042694620
39	Samath D Dharmaratne	https://orcid.org/0000-0003-4144-2107	https://openalex.org/A5032344410
40	Eric L. Ding	https://orcid.org/0000-0002-5881-8097	https://openalex.org/A5091864668
41	Adnan M Durrani	\N	https://openalex.org/A5109055704
42	Alireza Esteghamati	https://orcid.org/0000-0001-5114-3982	https://openalex.org/A5089768281
43	Farshad Farzadfar	https://orcid.org/0000-0001-8288-4046	https://openalex.org/A5035870050
44	Derek F J Fay	\N	https://openalex.org/A5113656294
45	Valery L. Feigin	https://orcid.org/0000-0002-6372-1740	https://openalex.org/A5052615582
46	Abraham D Flaxman	\N	https://openalex.org/A5108084990
47	Mohammad H Forouzanfar	https://orcid.org/0000-0001-9201-0991	https://openalex.org/A5107973303
48	Atsushi Goto	https://orcid.org/0000-0003-0669-654X	https://openalex.org/A5065856181
49	Mark Green	https://orcid.org/0000-0002-0942-6628	https://openalex.org/A5100633152
50	Tarun Gupta	https://orcid.org/0000-0003-0982-2927	https://openalex.org/A5028658441
51	Nima Hafezi‐Nejad	https://orcid.org/0000-0001-9052-450X	https://openalex.org/A5031337514
52	Graeme J. Hankey	https://orcid.org/0000-0002-6044-7328	https://openalex.org/A5014800121
53	Heather Harewood	https://orcid.org/0000-0002-4114-2342	https://openalex.org/A5090258107
54	Rasmus Havmoeller	\N	https://openalex.org/A5068079812
55	Simon I Hay	https://orcid.org/0000-0002-0611-7272	https://openalex.org/A5031889135
56	Lucía Hernández	\N	https://openalex.org/A5111862360
57	Abdullatif Husseini	https://orcid.org/0000-0001-8767-5956	https://openalex.org/A5106716299
58	Bulat Idrisov	https://orcid.org/0000-0002-1971-2572	https://openalex.org/A5075065752
59	Nayu Ikeda	\N	https://openalex.org/A5108145341
60	Farhad Islami	https://orcid.org/0000-0002-7357-5994	https://openalex.org/A5031129631
61	Eiman Jahangir	\N	https://openalex.org/A5074928240
62	Simerjot K Jassal	https://orcid.org/0000-0001-6781-2220	https://openalex.org/A5055310842
63	Sun Ha Jee	https://orcid.org/0000-0001-9519-3068	https://openalex.org/A5044597411
64	Mona Jeffreys	https://orcid.org/0000-0002-2617-0361	https://openalex.org/A5065323010
65	Jost B. Jonas	https://orcid.org/0000-0003-2972-5227	https://openalex.org/A5082561940
66	Edmond K. Kabagambe	https://orcid.org/0000-0002-8993-3186	https://openalex.org/A5080728144
67	Shams Eldin Ali Hassan Khalifa	https://orcid.org/0000-0002-8415-1556	https://openalex.org/A5001558444
68	André Pascal Kengne	https://orcid.org/0000-0002-5183-131X	https://openalex.org/A5016936793
69	Yousef Khader	https://orcid.org/0000-0002-7830-6857	https://openalex.org/A5059896659
70	Young‐Ho Khang	https://orcid.org/0000-0002-9585-8266	https://openalex.org/A5088103101
71	Daniel Kim	https://orcid.org/0000-0001-8907-6420	https://openalex.org/A5100372590
72	Ruth W Kimokoti	https://orcid.org/0000-0002-4980-3256	https://openalex.org/A5061451642
73	Jonas M Kinge	\N	https://openalex.org/A5110488137
74	Yoshihiro Kokubo	https://orcid.org/0000-0002-0705-9449	https://openalex.org/A5018175714
75	Soewarta Kosen	https://orcid.org/0000-0002-2517-8118	https://openalex.org/A5077849668
76	Gene F. Kwan	https://orcid.org/0000-0002-0929-6800	https://openalex.org/A5005970027
77	Taavi Lai	\N	https://openalex.org/A5109074641
78	Mall Leinsalu	https://orcid.org/0000-0003-4453-4760	https://openalex.org/A5033675266
79	Li Y	https://orcid.org/0000-0003-3842-475X	https://openalex.org/A5100391240
80	Xiaofeng Liang	https://orcid.org/0000-0001-8248-3816	https://openalex.org/A5100713957
81	Fei Liu	https://orcid.org/0000-0001-6093-0726	https://openalex.org/A5100394554
82	Giancarlo Logroscino	https://orcid.org/0000-0003-0423-3242	https://openalex.org/A5047104019
83	Paulo A. Lotufo	https://orcid.org/0000-0002-4856-8450	https://openalex.org/A5023008381
84	Yuan Lu	https://orcid.org/0000-0001-5264-2169	https://openalex.org/A5086448660
85	Jixiang Ma	\N	https://openalex.org/A5107836435
86	Nana Kwaku Mainoo	\N	https://openalex.org/A5025947251
87	George A. Mensah	https://orcid.org/0000-0002-0387-5326	https://openalex.org/A5014290409
88	Tony R. Merriman	https://orcid.org/0000-0003-0844-8726	https://openalex.org/A5008504111
89	Ali H. Mokdad	https://orcid.org/0000-0002-4994-3339	https://openalex.org/A5083535850
90	Joanna Moschandreas	\N	https://openalex.org/A5108098384
91	Mohsen Naghavi	https://orcid.org/0000-0002-6209-1513	https://openalex.org/A5011259455
92	Aliya Naheed	https://orcid.org/0000-0002-6016-5603	https://openalex.org/A5058729777
93	Devina Nand	\N	https://openalex.org/A5107921825
94	K M Venkat Narayan	\N	https://openalex.org/A5107834825
95	Erica L. Nelson	https://orcid.org/0000-0003-1696-443X	https://openalex.org/A5013877984
96	Marian L. Neuhouser	https://orcid.org/0000-0002-3876-0000	https://openalex.org/A5037632878
97	Muhammad Imran Nisar	https://orcid.org/0000-0002-2378-4720	https://openalex.org/A5090564291
98	Takayoshi Ohkubo	https://orcid.org/0000-0002-3283-8196	https://openalex.org/A5073636956
99	Samuel Oti	https://orcid.org/0000-0003-1035-9511	https://openalex.org/A5008234186
100	Andrea Pedroza-Tobías	https://orcid.org/0000-0002-7158-3667	https://openalex.org/A5061152273
101	Sarah Whitmee	https://orcid.org/0000-0001-9161-868X	https://openalex.org/A5017261520
102	Andy Haines	https://orcid.org/0000-0002-8053-4605	https://openalex.org/A5080652975
103	Chris Beyrer	https://orcid.org/0000-0003-0665-9124	https://openalex.org/A5015210998
104	Frederick Boltz	https://orcid.org/0000-0002-4225-248X	https://openalex.org/A5079731020
105	Anthony Capon	https://orcid.org/0000-0003-0354-6810	https://openalex.org/A5029854418
106	Braulio Ferreira de Souza Dias	https://orcid.org/0000-0003-3102-1560	https://openalex.org/A5104666891
107	Alex Ezeh	https://orcid.org/0000-0002-1309-4697	https://openalex.org/A5078245614
108	Howard Frumkin	https://orcid.org/0000-0001-7079-3534	https://openalex.org/A5022831485
109	Peng Gong	https://orcid.org/0000-0003-1513-3765	https://openalex.org/A5059264917
110	Peter Head	\N	https://openalex.org/A5108500547
111	Richard Horton	https://orcid.org/0000-0003-1792-5408	https://openalex.org/A5082599575
112	Georgina M. Mace	https://orcid.org/0000-0001-8965-5211	https://openalex.org/A5018062208
113	Robert Marten	https://orcid.org/0000-0002-2416-2309	https://openalex.org/A5059195585
114	Samuel S. Myers	https://orcid.org/0000-0002-5808-2454	https://openalex.org/A5031280274
115	Sania Nishtar	\N	https://openalex.org/A5051455916
116	Steven A. Osofsky	\N	https://openalex.org/A5112170397
117	Subhrendu K. Pattanayak	https://orcid.org/0000-0003-2021-5511	https://openalex.org/A5063396680
118	Montira J. Pongsiri	https://orcid.org/0000-0003-0034-3241	https://openalex.org/A5054773564
119	Cristina Romanelli	https://orcid.org/0000-0001-9429-6946	https://openalex.org/A5102745467
120	Agnès Soucat	https://orcid.org/0000-0002-7779-8079	https://openalex.org/A5029589901
121	Jeanette Vega	\N	https://openalex.org/A5113668879
122	Derek Yach	https://orcid.org/0000-0001-5667-6446	https://openalex.org/A5041574919
123	Susan M. Sawyer	https://orcid.org/0000-0002-9095-358X	https://openalex.org/A5054655408
124	Rima Afifi	https://orcid.org/0000-0003-3154-3617	https://openalex.org/A5005338810
125	Linda H. Bearinger	\N	https://openalex.org/A5109248863
126	Sarah‐Jayne Blakemore	https://orcid.org/0000-0002-1690-2805	https://openalex.org/A5050197307
127	Bruce Dick	https://orcid.org/0000-0003-0404-4927	https://openalex.org/A5027747326
128	George Patton	https://orcid.org/0000-0001-5039-8326	https://openalex.org/A5060032068
129	John G.F. Cleland	https://orcid.org/0000-0002-1471-7016	https://openalex.org/A5017160240
130	Stan Bernstein	\N	https://openalex.org/A5017496458
131	Aníbal Faúndes	https://orcid.org/0000-0003-4178-6030	https://openalex.org/A5074376229
132	Anna Glasier	https://orcid.org/0000-0002-5697-255X	https://openalex.org/A5005125409
133	Jolene Innis	\N	https://openalex.org/A5051974299
\.


--
-- Data for Name: experts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.experts (orcid, firstname, lastname, domains, fields, subfields) FROM stdin;
https://orcid.org/0000-0002-6004-3972	Anthony	Ajayi	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting","Biochemistry, Genetics and Molecular Biology",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0001-6205-3296	Beatrice	Maina	{"Social Sciences","Health Sciences"}	{"Social Sciences","Health Professions",Psychology,"Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-0735-9839	Caroline	Kabiru	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Decision Sciences","Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0001-7155-3786	Emmy	Igonya	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Arts and Humanities","Physics and Astronomy",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-1866-3905	Estelle	Sidze	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Computer Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0001-7742-9954	Kenneth	Juma	{"Social Sciences","Health Sciences"}	{"Business, Management and Accounting",Nursing,"Social Sciences","Health Professions",Psychology,"Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-7200-6116	Yohannes	Wado	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Arts and Humanities",Nursing,"Social Sciences","Health Professions",Psychology,"Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-6878-0627	Amanuel	Abajobir	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-3682-4744	Ramatou	Ouedraogo	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting","Arts and Humanities","Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences","Social Sciences","Health Professions",Psychology,"Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-0508-1773	Moses	Ngware	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Business, Management and Accounting","Decision Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-4206-9746	Patricia	Kitsao	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Arts and Humanities",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0001-8440-064X	Lucy	Wakiaga	{"Social Sciences"}	{"Social Sciences",Psychology}	{}
https://orcid.org/0000-0003-3550-4869	Lydia	Namatende	{"Social Sciences","Health Sciences"}	{"Arts and Humanities","Social Sciences","Health Professions",Psychology,"Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-1200-6042	Margaret	Nampijja	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Computer Science",Veterinary,Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science",Medicine}	{}
https://orcid.org/0000-0002-6439-7233	Amani	Karisa	{"Social Sciences","Health Sciences"}	{"Social Sciences","Health Professions",Psychology,"Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0001-9066-6065	Silas	Onyango	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Business, Management and Accounting","Decision Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0003-2465-0967	Benta	Abuya	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Decision Sciences","Arts and Humanities",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-0969-0699	Agnes	Kiragga	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Decision Sciences","Environmental Science",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-3907-1538	Daniel	Mwanga	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting","Decision Sciences","Biochemistry, Genetics and Molecular Biology","Environmental Science",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-4491-538X	Bonventure	Mwangi	{"Social Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology",Nursing,"Social Sciences","Health Professions","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-2366-2774	Samuel	Iddi	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting","Decision Sciences",Neuroscience,"Biochemistry, Genetics and Molecular Biology","Environmental Science","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-0903-5491	Alypio	Nyandwi	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Business, Management and Accounting","Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-6823-0895	Hesborn	Wao	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting","Decision Sciences",Engineering,Nursing,"Social Sciences","Health Professions",Psychology,"Economics, Econometrics and Finance",Medicine,"Pharmacology, Toxicology and Pharmaceutics",Mathematics}	{}
https://orcid.org/0000-0002-8381-6747	Marta	Vicente-Crespo	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Computer Science","Decision Sciences",Neuroscience,"Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-6748-4025	Florah	Karimi	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Business, Management and Accounting","Decision Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science",Medicine}	{}
https://orcid.org/0000-0002-9417-8947	Patrick	Owili	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology",Energy,"Biochemistry, Genetics and Molecular Biology",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-4948-2883	Michelle	Mbuthia	{"Social Sciences","Health Sciences"}	{"Business, Management and Accounting","Health Professions",Medicine,"Social Sciences"}	{}
https://orcid.org/0000-0002-3417-6536	Abdhalah	Ziraba	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Computer Science","Business, Management and Accounting",Engineering,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-2333-3054	Frederick	Wekesah	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0001-9137-8014	Elizabeth	Kemigisha	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting",Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0001-6348-9075	Richard	Sanya	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting",Engineering,Veterinary,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-9966-1153	Gershim	Asiki	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Computer Science","Business, Management and Accounting",Engineering,"Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-8693-1943	Shukri	Mohamed	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting","Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0001-6828-8301	Peter	Otieno	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Computer Science","Business, Management and Accounting","Arts and Humanities","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0009-0000-5201-7574	Veronica	Ojiambo	{"Social Sciences","Life Sciences","Health Sciences"}	{"Agricultural and Biological Sciences","Economics, Econometrics and Finance",Medicine,"Business, Management and Accounting"}	{}
https://orcid.org/0000-0001-5272-616X	Elizabeth	Kimani	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Computer Science","Business, Management and Accounting",Engineering,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-6606-6534	Calistus	Wilunda	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting",Neuroscience,Nursing,"Social Sciences","Health Professions",Psychology,"Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-4289-4762	Milka	Wanjohi	{"Social Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting",Veterinary,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-8334-601X	David	Osogo	{"Social Sciences","Health Sciences"}	{"Economics, Econometrics and Finance","Health Professions",Psychology}	{}
https://orcid.org/0000-0003-1849-4961	Antonina	Mutoro	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting",Energy,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science",Medicine}	{}
https://orcid.org/0000-0003-2535-7041	Jacqueline	Kungú	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting","Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science",Medicine}	{}
https://orcid.org/0000-0001-9095-4905	Alice	Karanja	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting",Engineering,Energy,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Environmental Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-5261-8481	Dickson	Amugsi	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting",Energy,Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-6188-196X	Blessing	Mberu	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Computer Science","Business, Management and Accounting",Energy,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-5641-5243	Caroline	Kabaria	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Computer Science",Engineering,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-6782-363X	Gloria	Lang'at	{"Social Sciences","Physical Sciences","Health Sciences"}	{Nursing,"Social Sciences","Health Professions",Psychology,"Computer Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-6733-1539	Razak	Gyasi	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Computer Science","Business, Management and Accounting",Engineering,"Arts and Humanities","Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance","Earth and Planetary Sciences",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-5166-5243	Kanyiva	Muindi	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting",Energy,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0003-3069-8967	Sheillah	Simiyu	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Computer Science",Engineering,"Business, Management and Accounting","Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-2364-4602	Innocent	Tumwebaze	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting",Engineering,"Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0001-5334-3793	Lynette	Kamau	{"Social Sciences","Life Sciences","Health Sciences"}	{"Biochemistry, Genetics and Molecular Biology",Nursing,"Social Sciences","Health Professions","Economics, Econometrics and Finance",Medicine}	{}
https://orcid.org/0000-0002-4028-0575	Cheikh	Faye	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Business, Management and Accounting",Engineering,Neuroscience,"Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions",Psychology,"Environmental Science","Economics, Econometrics and Finance",Medicine,Chemistry,Mathematics}	{}
https://orcid.org/0000-0003-4291-6773	Assane	Diouf	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Computer Science","Biochemistry, Genetics and Molecular Biology","Agricultural and Biological Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Chemistry,"Materials Science"}	{}
https://orcid.org/0000-0003-4945-0734	Anne	Njeri	{"Social Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology",Medicine,"Social Sciences","Health Professions"}	{}
https://orcid.org/0000-0003-1643-9934	Martin	Mutua	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-3711-8814	Sokhna	Thiam	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Business, Management and Accounting","Decision Sciences",Engineering,Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-1994-5170	Moustapha	Tall	{"Physical Sciences","Life Sciences"}	{"Environmental Science","Agricultural and Biological Sciences","Earth and Planetary Sciences"}	{}
https://orcid.org/0000-0001-5615-3127	Arsene	Sandie	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting","Decision Sciences",Nursing,"Social Sciences","Health Professions","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0003-1634-4708	El Hadji	Malick Sylla	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Agricultural and Biological Sciences","Social Sciences","Health Professions","Computer Science","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-3345-0636	Rodrigue	Nda’chi Deffo	{"Social Sciences","Physical Sciences","Life Sciences","Health Sciences"}	{"Immunology and Microbiology","Business, Management and Accounting",Nursing,"Social Sciences","Economics, Econometrics and Finance",Medicine,Mathematics}	{}
https://orcid.org/0000-0002-9915-1989	Rornald	Kananura Muhumuza	{"Social Sciences","Physical Sciences","Health Sciences"}	{"Computer Science","Decision Sciences",Nursing,"Social Sciences","Health Professions","Environmental Science","Economics, Econometrics and Finance",Medicine}	{}
\.


--
-- Data for Name: publication_tag; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.publication_tag (publication_doi, tag_id) FROM stdin;
https://doi.org/10.1016/s0140-6736(14)60460-8	1
https://doi.org/10.1016/s0140-6736(14)60460-8	2
https://doi.org/10.1016/s0140-6736(14)60460-8	3
https://doi.org/10.1016/s0140-6736(14)60460-8	4
https://doi.org/10.1016/s0140-6736(14)60460-8	5
https://doi.org/10.1016/s0140-6736(14)60460-8	6
https://doi.org/10.1016/s0140-6736(14)60460-8	7
https://doi.org/10.1016/s0140-6736(14)60460-8	8
https://doi.org/10.1016/s0140-6736(14)60460-8	9
https://doi.org/10.1016/s0140-6736(14)60460-8	10
https://doi.org/10.1016/s0140-6736(14)60460-8	11
https://doi.org/10.1016/s0140-6736(14)60460-8	12
https://doi.org/10.1016/s0140-6736(15)60901-1	13
https://doi.org/10.1016/s0140-6736(15)60901-1	14
https://doi.org/10.1016/s0140-6736(15)60901-1	15
https://doi.org/10.1016/s0140-6736(15)60901-1	16
https://doi.org/10.1016/s0140-6736(15)60901-1	17
https://doi.org/10.1016/s0140-6736(15)60901-1	18
https://doi.org/10.1016/s0140-6736(15)60901-1	19
https://doi.org/10.1016/s0140-6736(15)60901-1	20
https://doi.org/10.1016/s0140-6736(15)60901-1	21
https://doi.org/10.1016/s0140-6736(15)60901-1	22
https://doi.org/10.1016/s0140-6736(15)60901-1	23
https://doi.org/10.1016/s0140-6736(15)60901-1	24
https://doi.org/10.1016/s0140-6736(15)60901-1	25
https://doi.org/10.1016/s0140-6736(15)60901-1	26
https://doi.org/10.1016/s0140-6736(12)60072-5	7
https://doi.org/10.1016/s0140-6736(12)60072-5	27
https://doi.org/10.1016/s0140-6736(12)60072-5	28
https://doi.org/10.1016/s0140-6736(12)60072-5	29
https://doi.org/10.1016/s0140-6736(12)60072-5	30
https://doi.org/10.1016/s0140-6736(12)60072-5	31
https://doi.org/10.1016/s0140-6736(12)60072-5	32
https://doi.org/10.1016/s0140-6736(12)60072-5	3
https://doi.org/10.1016/s0140-6736(12)60072-5	33
https://doi.org/10.1016/s0140-6736(12)60072-5	8
https://doi.org/10.1016/s0140-6736(12)60072-5	9
https://doi.org/10.1016/s0140-6736(12)60072-5	34
https://doi.org/10.1016/s0140-6736(12)60072-5	12
https://doi.org/10.1016/s0140-6736(12)60072-5	35
https://doi.org/10.1016/s0140-6736(06)69480-4	36
https://doi.org/10.1016/s0140-6736(06)69480-4	19
https://doi.org/10.1016/s0140-6736(06)69480-4	37
https://doi.org/10.1016/s0140-6736(06)69480-4	6
https://doi.org/10.1016/s0140-6736(06)69480-4	38
https://doi.org/10.1016/s0140-6736(06)69480-4	39
https://doi.org/10.1016/s0140-6736(06)69480-4	40
https://doi.org/10.1016/s0140-6736(06)69480-4	41
https://doi.org/10.1016/s0140-6736(06)69480-4	42
https://doi.org/10.1016/s0140-6736(06)69480-4	18
https://doi.org/10.1016/s0140-6736(06)69480-4	43
https://doi.org/10.1016/s0140-6736(06)69480-4	44
https://doi.org/10.1016/s0140-6736(06)69480-4	16
https://doi.org/10.1016/s0140-6736(06)69480-4	3
https://doi.org/10.1016/s0140-6736(06)69480-4	45
https://doi.org/10.1016/s0140-6736(06)69480-4	25
https://doi.org/10.1016/s0140-6736(06)69480-4	8
https://doi.org/10.1016/s0140-6736(06)69480-4	46
https://doi.org/10.1016/s0140-6736(06)69480-4	26
https://doi.org/10.1016/s0140-6736(06)69480-4	47
https://doi.org/10.1016/s0140-6736(06)69480-4	48
\.


--
-- Data for Name: publications; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.publications (doi, title, abstract, summary) FROM stdin;
https://doi.org/10.1016/s0140-6736(14)60460-8	Global, regional, and national prevalence of overweight and obesity in children and adults during 1980–2013: a systematic analysis for the Global Burden of Disease Study 2013	Background In 2010, overweight and obesity were estimated to cause 3·4 million deaths, 3·9% of years of life lost, and 3·8% of disability-adjusted life-years (DALYs) worldwide. The rise in obesity has led to widespread calls for regular monitoring of changes in overweight and obesity prevalence in all populations. Comparable, up-to-date information about levels and trends is essential to quantify population health effects and to prompt decision makers to prioritise action. We estimate the global, regional, and national prevalence of overweight and obesity in children and adults during 1980–2013. Methods We systematically identified surveys, reports, and published studies (n=1769) that included data for height and weight, both through physical measurements and self-reports. We used mixed effects linear regression to correct for bias in self-reports. We obtained data for prevalence of obesity and overweight by age, sex, country, and year (n=19 244) with a spatiotemporal Gaussian process regression model to estimate prevalence with 95% uncertainty intervals (UIs). Findings Worldwide, the proportion of adults with a body-mass index (BMI) of 25 kg/m2 or greater increased between 1980 and 2013 from 28·8% (95% UI 28·4–29·3) to 36·9% (36·3–37·4) in men, and from 29·8% (29·3–30·2) to 38·0% (37·5–38·5) in women. Prevalence has increased substantially in children and adolescents in developed countries; 23·8% (22·9–24·7) of boys and 22·6% (21·7–23·6) of girls were overweight or obese in 2013. The prevalence of overweight and obesity has also increased in children and adolescents in developing countries, from 8·1% (7·7–8·6) to 12·9% (12·3–13·5) in 2013 for boys and from 8·4% (8·1–8·8) to 13·4% (13·0–13·9) in girls. In adults, estimated prevalence of obesity exceeded 50% in men in Tonga and in women in Kuwait, Kiribati, Federated States of Micronesia, Libya, Qatar, Tonga, and Samoa. Since 2006, the increase in adult obesity in developed countries has slowed down. Interpretation Because of the established health risks and substantial increases in prevalence, obesity has become a major global health challenge. Not only is obesity increasing, but no national success stories have been reported in the past 33 years. Urgent global action and leadership is needed to help countries to more effectively intervene. Funding Bill & Melinda Gates Foundation.	From 1980 to 2013, the prevalence of overweight and obesity has increased globally in both adults and children, with alarming rates in developing countries. Despite its severe health consequences, no country has reported a decrease in obesity prevalence in the past 33 years, highlighting the need for urgent global action.
https://doi.org/10.1016/s0140-6736(15)60901-1	Safeguarding human health in the Anthropocene epoch: report of The Rockefeller Foundation–Lancet Commission on planetary health	Far-reaching changes to the structure and function of the Earth's natural systems represent a growing threat to human health. And yet, global health has mainly improved as these changes have gathered pace. What is the explanation? As a Commission, we are deeply concerned that the explanation is straightforward and sobering: we have been mortgaging the health of future generations to realise economic and development gains in the present. By unsustainably exploiting nature's resources, human civilisation has flourished but now risks substantial health effects from the degradation of nature's life support systems in the future. Health effects from changes to the environment including climatic change, ocean acidification, land degradation, water scarcity, overexploitation of fisheries, and biodiversity loss pose serious challenges to the global health gains of the past several decades and are likely to become increasingly dominant during the second half of this century and beyond. These striking trends are driven by highly inequitable, inefficient, and unsustainable patterns of resource consumption and technological development, together with population growth. We identify three categories of challenges that have to be addressed to maintain and enhance human health in the face of increasingly harmful environmental trends. Firstly, conceptual and empathy failures (imagination challenges), such as an over-reliance on gross domestic product as a measure of human progress, the failure to account for future health and environmental harms over present day gains, and the disproportionate effect of those harms on the poor and those in developing nations. Secondly, knowledge failures (research and information challenges), such as failure to address social and environmental drivers of ill health, a historical scarcity of transdisciplinary research and funding, together with an unwillingness or inability to deal with uncertainty within decision making frameworks. Thirdly, implementation failures (governance challenges), such as how governments and institutions delay recognition and responses to threats, especially when faced with uncertainties, pooled common resources, and time lags between action and effect. Although better evidence is needed to underpin appropriate policies than is available at present, this should not be used as an excuse for inaction. Substantial potential exists to link action to reduce environmental damage with improved health outcomes for nations at all levels of economic development. This Commission identifies opportunities for action by six key constituencies: health professionals, research funders and the academic community, the UN and Bretton Woods bodies, governments, investors and corporate reporting bodies, and civil society organisations. Depreciation of natural capital and nature's subsidy should be accounted for so that economy and nature are not falsely separated. Policies should balance social progress, environmental sustainability, and the economy. To support a world population of 9–10 billion people or more, resilient food and agricultural systems are needed to address both undernutrition and overnutrition, reduce waste, diversify diets, and minimise environmental damage. Meeting the need for modern family planning can improve health in the short term—eg, from reduced maternal mortality and reduced pressures on the environment and on infrastructure. Planetary health offers an unprecedented opportunity for advocacy of global and national reforms of taxes and subsidies for many sectors of the economy, including energy, agriculture, water, fisheries, and health. Regional trade treaties should act to further incorporate the protection of health in the near and long term. Several essential steps need to be taken to transform the economy to support planetary health. These steps include a reduction of waste through the creation of products that are more durable and require less energy and materials to manufacture than those often produced at present; the incentivisation of recycling, reuse, and repair; and the substitution of hazardous materials with safer alternatives. Key messages1The concept of planetary health is based on the understanding that human health and human civilisation depend on flourishing natural systems and the wise stewardship of those natural systems. However, natural systems are being degraded to an extent unprecedented in human history.2Environmental threats to human health and human civilisation will be characterised by surprise and uncertainty. Our societies face clear and potent dangers that require urgent and transformative actions to protect present and future generations.3The present systems of governance and organisation of human knowledge are inadequate to address the threats to planetary health. We call for improved governance to aid the integration of social, economic, and environmental policies and for the creation, synthesis, and application of interdisciplinary knowledge to strengthen planetary health.4Solutions lie within reach and should be based on the redefinition of prosperity to focus on the enhancement of quality of life and delivery of improved health for all, together with respect for the integrity of natural systems. This endeavour will necessitate that societies address the drivers of environmental change by promoting sustainable and equitable patterns of consumption, reducing population growth, and harnessing the power of technology for change. 1The concept of planetary health is based on the understanding that human health and human civilisation depend on flourishing natural systems and the wise stewardship of those natural systems. However, natural systems are being degraded to an extent unprecedented in human history.2Environmental threats to human health and human civilisation will be characterised by surprise and uncertainty. Our societies face clear and potent dangers that require urgent and transformative actions to protect present and future generations.3The present systems of governance and organisation of human knowledge are inadequate to address the threats to planetary health. We call for improved governance to aid the integration of social, economic, and environmental policies and for the creation, synthesis, and application of interdisciplinary knowledge to strengthen planetary health.4Solutions lie within reach and should be based on the redefinition of prosperity to focus on the enhancement of quality of life and delivery of improved health for all, together with respect for the integrity of natural systems. This endeavour will necessitate that societies address the drivers of environmental change by promoting sustainable and equitable patterns of consumption, reducing population growth, and harnessing the power of technology for change. Despite present limitations, the Sustainable Development Goals provide a great opportunity to integrate health and sustainability through the judicious selection of relevant indicators relevant to human wellbeing, the enabling infrastructure for development, and the supporting natural systems, together with the need for strong governance. The landscape, ecosystems, and the biodiversity they contain can be managed to protect natural systems, and indirectly, reduce human disease risk. Intact and restored ecosystems can contribute to resilience (see panel 1 for glossary of terms used in this report), for example, through improved coastal protection (eg, through wave attenuation) and the ability of floodplains and greening of river catchments to protect from river flooding events by diverting and holding excess water.Panel 1GlossaryHolocene1International Commission on StratigraphyInternational stratigraphic chart.http://www.stratigraphy.org/ICSchart/ChronostratChart2013-01.pdfDate: 2013Google ScholarA geological epoch that began about 11 700 years ago and encompasses most of the time period during which humanity has grown and developed, including all its written history and development of major civilisations.Anthropocene2Crutzen PJ Geology of mankind.Nature. 2002; 415: 23Crossref PubMed Scopus (1931) Google ScholarThe proposed name for a new geological epoch demarcated as the time when human activities began to have a substantial global effect on the Earth's systems. The Anthropocene has to be yet formally recognised as a new geological epoch and several dates have been put forward to mark its beginning.Ecosystem3Millennium Ecosystem AssessmentEcosystems and human wellbeing: health synthesis.in: Corvalan C Hales S McMichael AJ Island Press, Washington DC2005Google ScholarA dynamic complex of plant, animal, and microorganism communities and the non-living environment acting as a functional unit.Ecosystem services4UKNEAThe UK National Ecosystem Assessment: technical report. United Nations Environment Programme's World Conservation Monitoring Centre, Cambridge, UK2011Google ScholarThe benefits provided by ecosystems that contribute to making human life both possible and worth living. Examples of ecosystem services include products such as food and clean water, regulation of floods, soil erosion, and disease outbreaks, and non-material benefits such as recreational and spiritual benefits in natural areas. The term services is usually used to encompass the tangible and intangible benefits that human beings obtain from ecosystems, which are sometimes separated into goods and services.Biodiversity5Millennium Ecosystem AssessmentBiodiversity.in: Mace G Masundire H Baillie J Millennium ecosystem assessment: current state and trends: findings of the condition and trends working group ecosystems and human well-being. Island Press, Washington, DC2005Google ScholarAn abbreviation of biological diversity; biodiversity means the variability among living organisms from all sources, including inter alia, terrestrial, marine, and other aquatic ecosystems and the ecological complexes of which they are part. This variability includes diversity within species, between species, and of ecosystems.Wetland6RamsarConvention on wetlands of international importance especially as waterfowl habitat 1971. Iran, Feb 2, 1971. As amended by the protocol of Dec 3, 1982, and the amendments of May 28, 1987.http://portal.unesco.org/en/ev.php-URL_ID=15398&URL_DO=DO_TOPIC&URL_SECTION=201.htmlGoogle ScholarThe Ramsar Convention defines wetlands as “areas of marsh, fen, peatland or water, whether natural or artificial, permanent or temporary, with water that is static or flowing, fresh, brackish or salt, including areas of marine water the depth of which at low tide does not exceed six metres”.Representative Concentration Pathway (RCP)7IPCCClimate change 2013. The Physical Science Basis Working Group I contribution to the fifth assessment report of the Intergovernmental Panel on Climate Change. Cambridge University Press, Intergovernmental Panel on Climate Change, Cambridge, UK and New York, USA2013Google ScholarRCPs are trajectories of the concentrations of greenhouse gases in the atmosphere consistent with a range of possible future emissions. For the Fifth Assessment Report of Intergovernmental Panel on Climate Change, the scientific community has defined a set of four RCPs. They are identified by their approximate total radiative forcing (ie, warming effect) in the year 2100 relative to 1750. RCP 8·5 is a pathway with very high greenhouse gas emissions, but such emissions are in line with present trends.Social–ecological systems8Stockholm Resilience CentreResilience dictionary.http://www.stockholmresilience.org/21/research/what-is-resilience/resilience-dictionary.htmlDate: 2015Google ScholarNatural systems do not exist without people and social systems cannot exist totally in isolation from nature. These systems are truly interconnected and coevolve across spatial and temporal scales.REDD+9UN-REDD ProgrammeAbout REDD+.http://www.un-redd.org/aboutreddDate: 2015Google ScholarReducing Emissions from Deforestation and Forest Degradation (REDD) tries to assign a financial value to the carbon stored in trees to help developing countries invest in low-carbon paths to sustainable development. REDD+ includes an added focus on conservation, sustainable management of forests, and enhancement of forest carbon stocks.Externalities10Buchanan JM Stubblebine WC Externality.Economica. 1962; 29: 371-384Crossref Google ScholarA benefit or cost that affects an individual or group of people who did not choose to incur that benefit or cost.Circular economy11European CommissionTowards a circular economy: a zero waste programme for Europe.http://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52014DC0398Date: 2014Google ScholarA global economic model that decouples economic growth and development from the consumption of finite resources. Circular economy systems keep products in use for as long as possible, allow for the recycling of end products, and eliminate waste.State shift12Rocha JC Biggs R Peterson GD Regime shifts: what are they and why do they matter?.http://www.regimeshifts.org/datasets-resources/Date: 2014Google ScholarLarge, lasting changes in the structure and function of social–ecological systems, with substantial impacts on the ecosystem services provided by these systems.Resilience8Stockholm Resilience CentreResilience dictionary.http://www.stockholmresilience.org/21/research/what-is-resilience/resilience-dictionary.htmlDate: 2015Google Scholar, 13Rodin J The resilience dividend: being strong in a world where things go wrong. PublicAffairs, New York2014Google Scholar“the capacity of any entity—an individual, a community, an organization, or a natural system—to prepare for disruptions, to recover from shocks and stresses, and to adapt and grow from a disruptive experience.” Holocene1International Commission on StratigraphyInternational stratigraphic chart.http://www.stratigraphy.org/ICSchart/ChronostratChart2013-01.pdfDate: 2013Google Scholar A geological epoch that began about 11 700 years ago and encompasses most of the time period during which humanity has grown and developed, including all its written history and development of major civilisations. Anthropocene2Crutzen PJ Geology of mankind.Nature. 2002; 415: 23Crossref PubMed Scopus (1931) Google Scholar The proposed name for a new geological epoch demarcated as the time when human activities began to have a substantial global effect on the Earth's systems. The Anthropocene has to be yet formally recognised as a new geological epoch and several dates have been put forward to mark its beginning. Ecosystem3Millennium Ecosystem AssessmentEcosystems and human wellbeing: health synthesis.in: Corvalan C Hales S McMichael AJ Island Press, Washington DC2005Google Scholar A dynamic complex of plant, animal, and microorganism communities and the non-living environment acting as a functional unit. Ecosystem services4UKNEAThe UK National Ecosystem Assessment: technical report. United Nations Environment Programme's World Conservation Monitoring Centre, Cambridge, UK2011Google Scholar The benefits provided by ecosystems that contribute to making human life both possible and worth living. Examples of ecosystem services include products such as food and clean water, regulation of floods, soil erosion, and disease outbreaks, and non-material benefits such as recreational and spiritual benefits in natural areas. The term services is usually used to encompass the tangible and intangible benefits that human beings obtain from ecosystems, which are sometimes separated into goods and services. Biodiversity5Millennium Ecosystem AssessmentBiodiversity.in: Mace G Masundire H Baillie J Millennium ecosystem assessment: current state and trends: findings of the condition and trends working group ecosystems and human well-being. Island Press, Washington, DC2005Google Scholar An abbreviation of biological diversity; biodiversity means the variability among living organisms from all sources, including inter alia, terrestrial, marine, and other aquatic ecosystems and the ecological complexes of which they are part. This variability includes diversity within species, between species, and of ecosystems. Wetland6RamsarConvention on wetlands of international importance especially as waterfowl habitat 1971. Iran, Feb 2, 1971. As amended by the protocol of Dec 3, 1982, and the amendments of May 28, 1987.http://portal.unesco.org/en/ev.php-URL_ID=15398&URL_DO=DO_TOPIC&URL_SECTION=201.htmlGoogle Scholar The Ramsar Convention defines wetlands as “areas of marsh, fen, peatland or water, whether natural or artificial, permanent or temporary, with water that is static or flowing, fresh, brackish or salt, including areas of marine water the depth of which at low tide does not exceed six metres”. Representative Concentration Pathway (RCP)7IPCCClimate change 2013. The Physical Science Basis Working Group I contribution to the fifth assessment report of the Intergovernmental Panel on Climate Change. Cambridge University Press, Intergovernmental Panel on Climate Change, Cambridge, UK and New York, USA2013Google Scholar RCPs are trajectories of the concentrations of greenhouse gases in the atmosphere consistent with a range of possible future emissions. For the Fifth Assessment Report of Intergovernmental Panel on Climate Change, the scientific community has defined a set of four RCPs. They are identified by their approximate total radiative forcing (ie, warming effect) in the year 2100 relative to 1750. RCP 8·5 is a pathway with very high greenhouse gas emissions, but such emissions are in line with present trends. Social–ecological systems8Stockholm Resilience CentreResilience dictionary.http://www.stockholmresilience.org/21/research/what-is-resilience/resilience-dictionary.htmlDate: 2015Google Scholar Natural systems do not exist without people and social systems cannot exist totally in isolation from nature. These systems are truly interconnected and coevolve across spatial and temporal scales. REDD+9UN-REDD ProgrammeAbout REDD+.http://www.un-redd.org/aboutreddDate: 2015Google Scholar Reducing Emissions from Deforestation and Forest Degradation (REDD) tries to assign a financial value to the carbon stored in trees to help developing countries invest in low-carbon paths to sustainable development. REDD+ includes an added focus on conservation, sustainable management of forests, and enhancement of forest carbon stocks. Externalities10Buchanan JM Stubblebine WC Externality.Economica. 1962; 29: 371-384Crossref Google Scholar A benefit or cost that affects an individual or group of people who did not choose to incur that benefit or cost. Circular economy11European CommissionTowards a circular economy: a zero waste programme for Europe.http://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52014DC0398Date: 2014Google Scholar A global economic model that decouples economic growth and development from the consumption of finite resources. Circular economy systems keep products in use for as long as possible, allow for the recycling of end products, and eliminate waste. State shift12Rocha JC Biggs R Peterson GD Regime shifts: what are they and why do they matter?.http://www.regimeshifts.org/datasets-resources/Date: 2014Google Scholar Large, lasting changes in the structure and function of social–ecological systems, with substantial impacts on the ecosystem services provided by these systems. Resilience8Stockholm Resilience CentreResilience dictionary.http://www.stockholmresilience.org/21/research/what-is-resilience/resilience-dictionary.htmlDate: 2015Google Scholar, 13Rodin J The resilience dividend: being strong in a world where things go wrong. PublicAffairs, New York2014Google Scholar “the capacity of any entity—an individual, a community, an organization, or a natural system—to prepare for disruptions, to recover from shocks and stresses, and to adapt and grow from a disruptive experience.” The growth in urban populations emphasises the importance of policies to improve health and the urban environment, such as through reduced air pollution, increased physical activity, provision of green space, and urban planning to prevent sprawl and decrease the magnitude of urban heat islands. Transdisciplinary research activities and capacity need substantial and urgent expansion. Present research limitations should not delay action. In situations where technology and knowledge can deliver win–win solutions and co-benefits, rapid scale-up can be achieved if researchers move ahead and assess the implementation of potential solutions. Recent scientific investments towards understanding non-linear state shifts in ecosystems are very important, but in the absence of improved understanding and predictability of such changes, efforts to improve resilience for human health and adaptation strategies remain a priority. The creation of integrated surveillance systems that collect rigorous health, socioeconomic, and environmental data for defined populations over long time periods can provide early detection of emerging disease outbreaks or changes in nutrition and non-communicable disease burden. The improvement of risk communication to policy makers and the public and the support of policy makers to make evidence-informed decisions can be helped by an increased capacity to do systematic reviews and the provision of rigorous policy briefs. Health professionals have an essential role in the achievement of planetary health: working across sectors to integrate policies that advance health and environmental sustainability, tackling health inequities, reducing the environmental impacts of health systems, and increasing the resilience of health systems and populations to environmental change. Humanity can be stewarded successfully through the 21st century by addressing the unacceptable inequities in health and wealth within the environmental limits of the Earth, but this will require the generation of new knowledge, implementation of wise policies, decisive action, and inspirational leadership. By most metrics, human health is better today than at any time in history. Life expectancy has soared from 47 years in 1950–1955, to 69 years in 2005–2010. Death rates in children younger than 5 years of age worldwide decreased substantially from 214 per thousand live births in 1950–1955 to 59 in 2005–2010.14You D Hug L Chen Y Wardlaw T Newby H Levels and trends in child mortality. United Nations Inter-agency Group for Child Mortality Estimation, New York2014Google Scholar, 15Population Division of the Department of Economic and Social Affairs of the UN SecretariatWorld population prospects: the 2012 revision. United Nations, New York2013Crossref Google Scholar Human beings have been supremely successful, staging a “great escape” from extreme deprivation in the past 250 years.16Deaton A The great escape: health, wealth, and the origins of inequality. Princeton University Press, Princeton2013Google Scholar The total number of people living in extreme poverty has fallen by 0·7 billion over the past 30 years, despite an increase in the total population of poor countries of about 2 billion.17Olinto P Beegle K Sobrado C Uematsu H The state of the poor: where are the poor, where is extreme poverty harder to end, and what is the current profile of the world's poor? The World Bank, Washington, DC2013Google Scholar This escape from poverty has been accompanied by unparalleled advances in public health, health care, education, human rights legislation, and technological development that have brought great benefits, albeit inequitably, to humanity. Humanity's progress has been supported by the Earth's ecological and biophysical systems. The Earth's atmosphere, oceans, and important ecosystems such as forests, wetlands, and tundra help to maintain a constant climate, provide clean air, recycle nutrients such as nitrogen and phosphorus, and regulate the world's water cycle, giving humanity freshwater for drinking and sanitation.3Millennium Ecosystem AssessmentEcosystems and human wellbeing: health synthesis.in: Corvalan C Hales S McMichael AJ Island Press, Washington DC2005Google Scholar The land, seas, and rivers, and the plants and animals they contain, also provide many direct goods and benefits—chiefly food, fuel, timber, and medicinal compounds (figure 1). Alongside the development of public health, the development of agriculture and industry have been major drivers of human success, harnessing the ability of the Earth to provide sustenance, shelter, and energy—underpinning the expansion of civilisation.18Sukhdev P Wittmer H Schröter-Schlaack C et al.Mainstreaming the economics of nature: a synthesis of the approach, conclusions and recommendations of TEEB. The Economics of Ecosystems and Biodiversity, Geneva2010Google Scholar To achieve the gains in nutrition, health, and energy use needed to reach a population of more than 7 billion people has required substantial changes in many of these systems, often affecting their structure and function at a cost to their ability to provide other vital services and to function in ways on which humanity has relied throughout history.19DeFries R Foley JA Asner GP Land-use choices: balancing human needs and ecosystem function.Front Ecol Environ. 2004; 2: 249-257Crossref Google Scholar In essence, humanity has traded off many of the Earth's supportive and regulating processes to feed and fuel human population growth and development.20Bennett EM Peterson GD Gordon LJ Understanding relationships among multiple ecosystem services.Ecol Lett. 2009; 12: 1394-1404Crossref PubMed Scopus (1166) Google Scholar The scale of human alteration of the natural world is difficult to overstate (figure 2). Human beings have converted about a third of the ice-free and desert-free land surface of the planet to cropland or pasture25Foley JA Monfreda C Ramankutty N Zaks D Our share of the planetary pie.Proc Natl Acad Sci USA. 2007; 104: 12585-12586Crossref PubMed Scopus (75) Google Scholar and annually roughly half of all accessible freshwater is appropriated for human use.22Steffen W Broadgate W Deutsch L Gaffney O Ludwig C The trajectory of the Anthropocene: the great acceleration.The Anthropocene Review. 2015; 2: 81-98Crossref Google Scholar Since 2000, human beings have cut down more than 2·3 million km2 of primary forest.26Hansen MC Potapov PV Moore R et al.High-resolution global maps of 21st-century forest cover change.Science. 2013; 342: 850-853Crossref PubMed Scopus (4290) Google Scholar About 90% of monitored fisheries are harvested at, or beyond, maximum sustainable yield limits.27FAOThe state of world fisheries and aquaculture—opportunities and challenges. Food and Agriculture Organization, Rome2014Google Scholar In the quest for energy and control over water resources, humanity has dammed more than 60% of the world's rivers,28World Commission on DamsDams and development: a new framework for decision-making.http://www.unep.org/dams/WCD/report/WCD_DAMS%20report.pdfDate: November, 2000Google Scholar affecting in excess of 0·5 million km of river.29Lehner B Liermann CR Revenga C et al.High-resolution mapping of the world's reservoirs and dams for sustainable river-flow management.Front Ecol Environ. 2011; 9: 494-502Crossref Scopus (0) Google Scholar Humanity is driving species to extinction at a rate that is more than 100 times that observed in the fossil record30Pimm SL Jenkins CN Abell R et al.The biodiversity of species and their rates of extinction, distribution, and protection.Science. 2014; 344: 1246752Crossref PubMed Scopus (1212) Google Scholar and many remaining species are decreasing in number. The 2014 Living Planet Report24WWFLiving planet report 2014: species and spaces, people and places. World Wide Fund for Nature, Gland, Switzerland2014Google Scholar estimates that vertebrate species have, on average, had their population sizes cut in half in the past 45 years. The concentrations of major greenhouse gases—carbon dioxide, methane, and nitrous oxide—are at their highest levels for at least the past 800 000 years.7IPCCClimate change 2013. The Physical Science Basis Working Group I contribution to the fifth assessment report of the Intergovernmental Panel on Climate Change. Cambridge University Press, Intergovernmental Panel on Climate Change, Cambridge, UK and New York, USA2013Google Scholar As a consequence of these actions, humanity has become a primary determinant of Earth's biophysical conditions, giving rise to a new term for the present geological epoch, the Anthropocene (panel 1).2Crutzen PJ Geology of mankind.Nature. 2002; 415: 23Crossref PubMed Scopus (1931) Google Scholar In 2005, a landmark study by the Millennium Ecosystem Assessment (MEA) estimated that 60% of ecosystem services examined, from regulation of air quality to purification of water, are being degraded or used unsustainably (figure 2).3Millennium Ecosystem AssessmentEcosystems and human wellbeing: health synthesis.in: Corvalan C Hales S McMichael AJ Island Press, Washington DC2005Google Scholar The authors of the MEA warned that “the ability of the planet's ecosystems to sustain future generations can no longer be taken for granted”.31Millennium Ecosystem AssessmentLiving beyond our means. Natural assets and human well-being. Statement from the Board.in: Millennium Ecosystem Assessment Board Millennium Ecosystem Assessment, Washington, DC2005Google Scholar In 2006, a report published by WHO estimated that about a quarter of the global disease burden and more than a third of the burden in children was attributable to modifiable environmental factors.32Prüss-Üstün A Corvalán C Preventing disease through healthy environments. Towards an estimate of the environmental burden of disease. World Health	Human activities are significantly altering Earth's natural systems, threatening human health and well-being. This environmental degradation poses challenges to achieving global health gains and requires urgent action to protect the health of present and future generations. The report calls for transformative actions, including redefining prosperity, promoting sustainable consumption, reducing population growth, and harnessing technology for positive change.
https://doi.org/10.1016/s0140-6736(12)60072-5	Adolescence: a foundation for future health	N/A	No abstract available for summarization
https://doi.org/10.1016/s0140-6736(06)69480-4	Family planning: the unfinished agenda	N/A	No abstract available for summarization
\.


--
-- Data for Name: query_history; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.query_history (query_id, query, "timestamp", result_count, search_type) FROM stdin;
\.


--
-- Data for Name: tags; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tags (tag_id, tag_name) FROM stdin;
1	field_of_study:Overweight
2	field_of_study:Obesity
3	field_of_study:Medicine
4	field_of_study:Body mass index
5	field_of_study:Demography
6	field_of_study:Population
7	field_of_study:Public health
8	field_of_study:Environmental health
9	field_of_study:Gerontology
10	field_of_study:Internal medicine
11	field_of_study:Sociology
12	field_of_study:Nursing
13	field_of_study:Natural resource economics
14	field_of_study:Global health
15	field_of_study:Planetary boundaries
16	field_of_study:Development economics
17	field_of_study:Environmental resource management
18	field_of_study:Political science
19	field_of_study:Economic growth
20	field_of_study:Environmental planning
21	field_of_study:Business
22	field_of_study:Geography
23	field_of_study:Health care
24	field_of_study:Sustainable development
25	field_of_study:Economics
26	field_of_study:Law
27	field_of_study:Social determinants of health
28	field_of_study:Adolescent health
29	field_of_study:Developmental psychology
30	field_of_study:Race and health
31	field_of_study:Affect (linguistics)
32	field_of_study:Mental health
33	field_of_study:Psychology
34	field_of_study:Psychiatry
35	field_of_study:Communication
36	field_of_study:Family planning
37	field_of_study:Poverty
38	field_of_study:Family planning policy
39	field_of_study:Developing country
40	field_of_study:Sustainability
41	field_of_study:Empowerment
42	field_of_study:Fertility
43	field_of_study:Total fertility rate
44	field_of_study:Promotion (chess)
45	field_of_study:Politics
46	field_of_study:Ecology
47	field_of_study:Research methodology
48	field_of_study:Biology
\.


--
-- Data for Name: term_frequencies; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.term_frequencies (term_id, term, frequency, last_updated) FROM stdin;
\.


--
-- Name: authors_author_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.authors_author_id_seq', 133, true);


--
-- Name: query_history_query_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.query_history_query_id_seq', 1, false);


--
-- Name: tags_tag_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tags_tag_id_seq', 48, true);


--
-- Name: term_frequencies_term_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.term_frequencies_term_id_seq', 1, false);


--
-- Name: author_publication author_publication_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.author_publication
    ADD CONSTRAINT author_publication_pkey PRIMARY KEY (author_id, doi);


--
-- Name: authors authors_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.authors
    ADD CONSTRAINT authors_pkey PRIMARY KEY (author_id);


--
-- Name: experts experts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.experts
    ADD CONSTRAINT experts_pkey PRIMARY KEY (orcid);


--
-- Name: publication_tag publication_tag_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.publication_tag
    ADD CONSTRAINT publication_tag_pkey PRIMARY KEY (publication_doi, tag_id);


--
-- Name: publications publications_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.publications
    ADD CONSTRAINT publications_pkey PRIMARY KEY (doi);


--
-- Name: query_history query_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.query_history
    ADD CONSTRAINT query_history_pkey PRIMARY KEY (query_id);


--
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (tag_id);


--
-- Name: term_frequencies term_frequencies_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.term_frequencies
    ADD CONSTRAINT term_frequencies_pkey PRIMARY KEY (term_id);


--
-- Name: term_frequencies term_frequencies_term_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.term_frequencies
    ADD CONSTRAINT term_frequencies_term_key UNIQUE (term);


--
-- Name: authors unique_author; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.authors
    ADD CONSTRAINT unique_author UNIQUE (name, orcid, author_identifier);


--
-- Name: idx_query_history_query; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_query_history_query ON public.query_history USING btree (query text_pattern_ops);


--
-- Name: idx_query_history_timestamp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_query_history_timestamp ON public.query_history USING btree ("timestamp" DESC);


--
-- Name: idx_term_frequencies_term; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_term_frequencies_term ON public.term_frequencies USING btree (term);


--
-- Name: author_publication author_publication_author_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.author_publication
    ADD CONSTRAINT author_publication_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.authors(author_id) ON DELETE CASCADE;


--
-- Name: author_publication author_publication_doi_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.author_publication
    ADD CONSTRAINT author_publication_doi_fkey FOREIGN KEY (doi) REFERENCES public.publications(doi) ON DELETE CASCADE;


--
-- Name: publication_tag publication_tag_publication_doi_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.publication_tag
    ADD CONSTRAINT publication_tag_publication_doi_fkey FOREIGN KEY (publication_doi) REFERENCES public.publications(doi) ON DELETE CASCADE;


--
-- Name: publication_tag publication_tag_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.publication_tag
    ADD CONSTRAINT publication_tag_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(tag_id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

