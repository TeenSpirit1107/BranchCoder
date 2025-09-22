import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

// 导入翻译文件
import enTranslation from '../assets/locales/en.json';
import zhTranslation from '../assets/locales/zh.json';

i18n
  .use(initReactI18next)
  .init({
    resources: {
      en: {
        translation: enTranslation,
      },
      zh: {
        translation: zhTranslation,
      },
    },
    lng: localStorage.getItem('language') || 'zh', // 默认语言
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // 不转义React中的内容
    },
  });

export default i18n; 